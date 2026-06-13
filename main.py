from flask import Flask, request, jsonify, send_from_directory
import os
import json
import requests
import re
import db_manager

app = Flask(__name__, static_folder='static')

# Initialize DB on startup
db_manager.init_db()

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    if request.method == 'GET':
        return jsonify(db_manager.get_settings())
    else:
        data = request.json or {}
        api_key = data.get('api_key', '').strip()
        dietary_pref = data.get('dietary_preferences', 'none').strip()
        budget_default = float(data.get('budget_default', 25.0))
        
        db_manager.save_settings(api_key, dietary_pref, budget_default)
        return jsonify({"status": "success", "message": "Settings saved successfully"})

@app.route('/api/meal-plans', methods=['GET'])
def get_meal_plans():
    return jsonify(db_manager.get_meal_plans())

@app.route('/api/meal-plans/<int:plan_id>', methods=['GET', 'DELETE'])
def meal_plan_details(plan_id):
    if request.method == 'GET':
        details = db_manager.get_meal_plan_details(plan_id)
        if details:
            return jsonify(details)
        return jsonify({"error": "Meal plan not found"}), 404
    else:
        db_manager.delete_meal_plan(plan_id)
        return jsonify({"status": "success", "message": "Meal plan deleted"})

@app.route('/api/todos/toggle', methods=['POST'])
def toggle_todo_item():
    data = request.json or {}
    todo_id = data.get('todo_id')
    is_completed = data.get('is_completed', False)
    
    if todo_id is None:
        return jsonify({"error": "Missing todo_id"}), 400
        
    db_manager.toggle_todo(todo_id, is_completed)
    return jsonify({"status": "success"})

@app.route('/api/todos/custom', methods=['POST'])
def add_custom_todo_item():
    data = request.json or {}
    plan_id = data.get('plan_id')
    task_name = data.get('task_name', '').strip()
    category = data.get('category', 'custom').strip()
    
    if not plan_id or not task_name:
        return jsonify({"error": "Missing plan_id or task_name"}), 400
        
    todo = db_manager.add_custom_todo(plan_id, task_name, category)
    return jsonify(todo)

@app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo_item(todo_id):
    db_manager.delete_todo(todo_id)
    return jsonify({"status": "success", "message": "Todo deleted"})

@app.route('/api/generate', methods=['POST'])
def generate_plan():
    data = request.json or {}
    day_description = data.get('day_description', '').strip()
    dietary_pref = data.get('dietary_preferences', 'none').strip()
    budget = float(data.get('budget', 25.0))
    
    if not day_description:
        return jsonify({"error": "Please describe your day!"}), 400
        
    # Get settings to check API Key
    settings = db_manager.get_settings()
    api_key = settings.get('api_key', '').strip()
    
    plan_data = None
    is_mock = True
    api_error = None
    
    if api_key:
        try:
            plan_data = generate_ai_plan(api_key, day_description, dietary_pref, budget)
            is_mock = False
        except Exception as e:
            api_error = str(e)
            print(f"Gemini API Error: {e}. Falling back to high-quality mock data.")
            
    if is_mock:
        plan_data = generate_mock_plan(day_description, dietary_pref, budget)
        if api_error:
            plan_data["budget_notes"] = f"⚠️ Gemini API Request failed ({api_error}). Using local generator. \n\n" + plan_data["budget_notes"]
        else:
            plan_data["budget_notes"] = "ℹ️ Operating in Demo Mode (No API key saved in settings). \n\n" + plan_data["budget_notes"]
            
    # Save plan and todos to database
    try:
        plan_id = db_manager.save_meal_plan(
            day_description=day_description,
            breakfast=plan_data["breakfast"],
            lunch=plan_data["lunch"],
            dinner=plan_data["dinner"],
            grocery_list=plan_data["grocery_list"],
            substitutions=plan_data["substitutions"],
            budget_target=budget,
            budget_estimated=plan_data["budget_estimated"],
            budget_status=plan_data["budget_status"],
            budget_notes=plan_data["budget_notes"],
            todo_items=plan_data["todo_items"]
        )
        
        # Get full saved plan details
        saved_plan = db_manager.get_meal_plan_details(plan_id)
        saved_plan["is_mock"] = is_mock
        return jsonify(saved_plan)
    except Exception as e:
        return jsonify({"error": f"Failed to save meal plan: {str(e)}"}), 500

def generate_ai_plan(api_key, day_description, dietary_pref, budget):
    """Call Gemini 1.5 Flash API to get structured meal plan and todos."""
    prompt = f"""
You are an expert AI meal planner and culinary assistant. Generate a highly personalized meal plan and cooking checklist based on:
- User's Day: "{day_description}"
- Dietary Preference: "{dietary_pref}"
- Target Budget: ${budget:.2f}

You MUST return a JSON object with exactly this structure:
{{
  "breakfast": "Name of breakfast & quick description (tailored to time constraints of user's morning)",
  "lunch": "Name of lunch & quick description (tailored to time constraints of user's midday)",
  "dinner": "Name of dinner & quick description (tailored to time constraints of user's evening)",
  "grocery_list": [
    {{"item": "item name", "estimated_cost": 3.50, "unit": "pack/lb/qty"}},
    ...
  ],
  "substitutions": [
    {{"original": "original ingredient", "substitute": "substitute ingredient", "reason": "why swap? (allergen, cost-saving, vegetarian conversion)"}},
    ...
  ],
  "budget_estimated": 22.50, // Sum of estimated_cost in grocery_list
  "budget_status": "under", // "under", "within", or "over" compared to budget target ${budget}
  "budget_notes": "A brief explanation of budget feasibility, price breakdown details, and recommendations.",
  "todo_items": [
    {{"task_name": "Highly actionable task. Example: Buy spinach, avocado, bread, eggs", "category": "grocery"}},
    {{"task_name": "Prep action. Example: Chop onions and tomatoes for dinner", "category": "prep"}},
    {{"task_name": "Cooking action. Example: Boil pasta for lunch", "category": "cooking"}}
  ]
}}

Guidelines:
1. Breakfast, lunch, and dinner must suit the user's described day (e.g. if they are rushed, keep breakfast/lunch instant, or suggest prepping dinner the night before).
2. The grocery list estimated costs should be realistic.
3. The budget_status is "under" if estimated <= budget * 0.9, "within" if budget * 0.9 < estimated <= budget, and "over" if estimated > budget.
4. Ensure tasks in todo_items are clear, actionable, and categorized.
5. Return ONLY the JSON object. Do not enclose it in markdown blocks or write conversational preambles.
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=20)
    
    if response.status_code != 200:
        raise Exception(f"Gemini API returned code {response.status_code}: {response.text}")
        
    response_json = response.json()
    try:
        text_content = response_json["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise Exception("Failed to parse completion text from Gemini response structure.")
        
    # Clean up text if LLM still returned markdown code blocks
    cleaned_text = text_content.strip()
    if cleaned_text.startswith("```"):
        # remove ```json and ```
        cleaned_text = re.sub(r"^```(?:json)?\n", "", cleaned_text)
        cleaned_text = re.sub(r"\n```$", "", cleaned_text)
        cleaned_text = cleaned_text.strip()
        
    try:
        plan_data = json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        raise Exception(f"API response was not valid JSON: {cleaned_text[:200]}...")
        
    # Validation of fields
    required = ["breakfast", "lunch", "dinner", "grocery_list", "substitutions", "budget_estimated", "budget_status", "budget_notes", "todo_items"]
    for field in required:
        if field not in plan_data:
            # fill with empty default
            if field in ["grocery_list", "substitutions", "todo_items"]:
                plan_data[field] = []
            elif field in ["budget_estimated"]:
                plan_data[field] = 0.0
            else:
                plan_data[field] = ""
                
    return plan_data

def generate_mock_plan(day_description, dietary_pref, budget):
    """Fallback high-quality mock data generator based on keywords."""
    desc_lower = day_description.lower()
    pref_lower = dietary_pref.lower()
    
    # Check for keywords to select template
    if "busy" in desc_lower or "rush" in desc_lower or "work" in desc_lower or "quick" in desc_lower:
        plan = get_busy_day_template(pref_lower)
    elif "workout" in desc_lower or "gym" in desc_lower or "protein" in desc_lower or "fitness" in desc_lower:
        plan = get_fitness_day_template(pref_lower)
    elif "cheap" in desc_lower or "budget" in desc_lower or "save" in desc_lower:
        plan = get_budget_day_template(pref_lower)
    else:
        # Default: Relaxed Weekend template
        plan = get_relaxed_day_template(pref_lower)
        
    # Recalculate budget feasibility dynamically
    total_cost = sum(item["estimated_cost"] for item in plan["grocery_list"])
    plan["budget_estimated"] = round(total_cost, 2)
    
    if total_cost <= budget * 0.9:
        plan["budget_status"] = "under"
        plan["budget_notes"] = f"Your daily budget is ${budget:.2f}. The estimated grocery cost is ${total_cost:.2f}, leaving you with ${budget - total_cost:.2f} savings! This plan is highly feasible and budget-friendly."
    elif total_cost <= budget:
        plan["budget_status"] = "within"
        plan["budget_notes"] = f"Your daily budget is ${budget:.2f}. The estimated grocery cost is ${total_cost:.2f}. You are within budget! Pro tip: buy bulk grains to save extra."
    else:
        plan["budget_status"] = "over"
        plan["budget_notes"] = f"Your daily budget is ${budget:.2f}, but groceries are estimated at ${total_cost:.2f} (${total_cost - budget:.2f} over). To fit your budget, consider using the suggested substitutions (e.g. swapping salmon for tofu or chicken for black beans) to save around $5.00!"
        
    return plan

def get_busy_day_template(pref):
    # Busy workday
    veg = pref in ["vegetarian", "vegan"]
    gluten_free = "gluten" in pref
    
    breakfast = "High-Fiber Berry Oatmeal Bowl" if veg else "Quick Greek Yogurt Parfait with Honey & Granola"
    lunch = "Hummus, Avocado, & Spinach Wrap" if veg else "Turkey, Avocado & Swiss Spinach Wrap"
    dinner = "Sheet-Pan Tofu with Roasted Broccoli & Chickpeas" if veg else "Sheet-Pan Garlic Chicken Breast with Broccoli & Carrots"
    
    if gluten_free:
        breakfast = "Berry Almond Milk Smoothie Bowl with Flax Seeds"
        lunch = "Quinoa Salad Bowl with Cucumber, Chickpeas, and Avocado"
        dinner = "Sheet-Pan Garlic Salmon (or Tofu) with Broccoli & Sweet Potato Cubes"

    grocery = [
        {"item": "Oats / Gluten-Free Oats" if gluten_free else "Granola & Honey", "estimated_cost": 2.50, "unit": "1 box"},
        {"item": "Greek Yogurt (or Almond Yogurt)" if veg or gluten_free else "Greek Yogurt", "estimated_cost": 3.00, "unit": "1 tub"},
        {"item": "Fresh Mixed Berries", "estimated_cost": 4.00, "unit": "1 pint"},
        {"item": "Avocado & Spinach", "estimated_cost": 3.50, "unit": "1 bag"},
        {"item": "Tortilla Wraps (Gluten-Free if needed)" if not gluten_free else "Quinoa", "estimated_cost": 2.80, "unit": "1 pack"},
        {"item": "Hummus", "estimated_cost": 2.50, "unit": "1 tub"},
        {"item": "Tofu & Chickpeas" if veg else "Chicken Breasts & Broccoli", "estimated_cost": 6.50 if veg else 8.50, "unit": "1 lb"}
    ]
    
    subs = [
        {"original": "Chicken Breasts", "substitute": "Extra Firm Tofu / Canned Chickpeas", "reason": "Vegetarian high-protein alternatives that cook quickly on sheet pans."},
        {"original": "Tortilla Wraps", "substitute": "Large Lettuce Leaves", "reason": "Reduces carbs and solves gluten-free constraints instantly."},
        {"original": "Greek Yogurt", "substitute": "Coconut or Soy Yogurt", "reason": "Dairy-free alternative."}
    ]
    
    todos = [
        {"task_name": "Shop for groceries (chicken/tofu, wraps, hummus, yogurt, berries, greens)", "category": "grocery"},
        {"task_name": "Wash spinach and broccoli; chop broccoli florets", "category": "prep"},
        {"task_name": "Pre-portion oats/yogurt and berries for breakfast", "category": "prep"},
        {"task_name": "Assemble wrap for lunch (hummus, avocado, spinach, turkey/tofu)", "category": "cooking"},
        {"task_name": "Toss chicken/tofu & broccoli in olive oil, spices, and bake on sheet pan (25 min @ 400°F)", "category": "cooking"}
    ]
    
    return {
        "breakfast": breakfast,
        "lunch": lunch,
        "dinner": dinner,
        "grocery_list": grocery,
        "substitutions": subs,
        "todo_items": todos
    }

def get_fitness_day_template(pref):
    # High protein / workout
    veg = pref in ["vegetarian", "vegan"]
    gluten_free = "gluten" in pref
    
    breakfast = "Protein Power Green Smoothie (Whey/Plant protein, banana, peanut butter, almond milk)"
    lunch = "Mediterranean Quinoa Salad Bowl with Feta & Roasted Chickpeas" if veg else "Seared Tuna Salad Quinoa Bowl with Boiled Egg"
    dinner = "Spiced Pan-Seared Salmon with Sweet Potatoes & Asparagus" if veg else "Lemon Herb Chicken Breast with Sweet Potatoes & Green Beans"
    
    if veg:
        dinner = "Cajun Tempeh Steaks with Sweet Potatoes & Roasted Asparagus"

    grocery = [
        {"item": "Protein Powder (Whey or Pea Protein)", "estimated_cost": 4.50, "unit": "Sample Pack"},
        {"item": "Almond Milk & Bananas", "estimated_cost": 2.20, "unit": "1 bundle"},
        {"item": "Quinoa & Canned Chickpeas", "estimated_cost": 3.00, "unit": "1 box/can"},
        {"item": "Feta Cheese & Olives" if veg else "Canned Tuna & Eggs", "estimated_cost": 3.80, "unit": "1 pack"},
        {"item": "Tempeh" if veg else ("Salmon Filets" if "Salmon" in dinner else "Chicken Breasts"), "estimated_cost": 4.50 if veg else 9.50, "unit": "1 lb"},
        {"item": "Sweet Potatoes & Asparagus / Green Beans", "estimated_cost": 4.00, "unit": "1 bag"}
    ]
    
    subs = [
        {"original": "Salmon Filet", "substitute": "Firm Tofu Steaks / Tempeh", "reason": "More budget-friendly and fully plant-based high protein alternative."},
        {"original": "Asparagus", "substitute": "Broccoli or Green Beans", "reason": "Saves $2.00 on average and contains similar micronutrients."},
        {"original": "Almond Milk", "substitute": "Water or Soy Milk", "reason": "Saves costs or increases protein density."}
    ]
    
    todos = [
        {"task_name": "Shop for groceries (protein powder, bananas, greens, quinoa, eggs/tuna, salmon/chicken/tempeh, sweet potatoes)", "category": "grocery"},
        {"task_name": "Boil 1 cup of quinoa; boil eggs if using for lunch", "category": "prep"},
        {"task_name": "Peel and cube sweet potatoes, snap ends off asparagus", "category": "prep"},
        {"task_name": "Blend green smoothie bowl for breakfast (protein, banana, spinach, peanut butter)", "category": "cooking"},
        {"task_name": "Toss quinoa with chickpeas, olives, feta/tuna, and lemon dressing for lunch", "category": "cooking"},
        {"task_name": "Pan-sear salmon/chicken/tempeh in olive oil, roast sweet potato cubes (20 min)", "category": "cooking"}
    ]
    
    return {
        "breakfast": breakfast,
        "lunch": lunch,
        "dinner": dinner,
        "grocery_list": grocery,
        "substitutions": subs,
        "todo_items": todos
    }

def get_budget_day_template(pref):
    # Budget day
    veg = pref in ["vegetarian", "vegan"]
    
    breakfast = "Classic Scrambled Eggs (or Tofu Scramble) on Buttered Toast"
    lunch = "Tex-Mex Rice, Black Bean & Corn Bowls with Cilantro Lime Dressing"
    dinner = "Garlic Tomato Spaghetti with Spinach & White Cannellini Beans"
    
    grocery = [
        {"item": "Carton of Eggs (or Block of Tofu)", "estimated_cost": 2.20, "unit": "1 pack"},
        {"item": "Loaf of Bread (Whole Wheat / Gluten-Free)", "estimated_cost": 1.80, "unit": "1 loaf"},
        {"item": "Long Grain White Rice", "estimated_cost": 1.20, "unit": "1 bag"},
        {"item": "Canned Black Beans & Sweet Corn", "estimated_cost": 1.60, "unit": "2 cans"},
        {"item": "Spaghetti Pasta", "estimated_cost": 1.00, "unit": "1 pack"},
        {"item": "Canned Crushed Tomatoes & Garlic", "estimated_cost": 1.50, "unit": "1 can/bulb"},
        {"item": "Fresh Cilantro & Lime", "estimated_cost": 1.00, "unit": "1 bunch"},
        {"item": "Fresh Spinach & Cannellini Beans", "estimated_cost": 2.00, "unit": "1 bag/can"}
    ]
    
    subs = [
        {"original": "Spaghetti", "substitute": "Brown Rice or Chickpea Pasta", "reason": "Increases fiber / gluten-free option."},
        {"original": "Eggs", "substitute": "Scrambled Silken Tofu", "reason": "Fully plant-based and similar price point."},
        {"original": "Canned beans", "substitute": "Dry beans (soaked overnight)", "reason": "Cuts cost of beans by 60% if prepped ahead."}
    ]
    
    todos = [
        {"task_name": "Shop for groceries (eggs/tofu, bread, rice, beans, pasta, canned tomatoes, garlic, greens)", "category": "grocery"},
        {"task_name": "Cook a batch of white rice; rinse black beans and corn", "category": "prep"},
        {"task_name": "Mince garlic cloves, chop fresh cilantro", "category": "prep"},
        {"task_name": "Cook scrambled eggs/tofu in butter/oil, serve on warm toasted bread", "category": "cooking"},
        {"task_name": "Assemble Tex-Mex bowls (rice, black beans, corn, cilantro, lime juice)", "category": "cooking"},
        {"task_name": "Boil pasta; simmer crushed tomatoes with garlic, toss with spinach and white beans, combine with pasta", "category": "cooking"}
    ]
    
    return {
        "breakfast": breakfast,
        "lunch": lunch,
        "dinner": dinner,
        "grocery_list": grocery,
        "substitutions": subs,
        "todo_items": todos
    }

def get_relaxed_day_template(pref):
    # Relaxed / gourmet weekend
    veg = pref in ["vegetarian", "vegan"]
    gluten_free = "gluten" in pref
    
    breakfast = "Buttermilk Blueberry Pancakes with Scrambled Eggs" if not veg else "Blueberry Oatmeal Pancakes with Maple Syrup"
    lunch = "Caprese Panini with Pesto, Fresh Mozzarella & Sliced Tomatoes"
    dinner = "Rustic Lentil & Vegetable Stew with Herbs" if veg else "Slow-Simmered Beef & Vegetable Stew with Red Wine Sauce"
    
    if gluten_free:
        breakfast = "Gluten-Free Banana Pancakes with Maple Syrup & Eggs"
        lunch = "Caprese Salad Salad Bowl with Pesto Dressing"
        dinner = "Slow-Cooked Herb Chicken (or Tofu) Stew with Carrots & Potatoes"

    grocery = [
        {"item": "Blueberries & Pancake Mix", "estimated_cost": 3.80, "unit": "1 pack"},
        {"item": "Fresh Eggs & Butter", "estimated_cost": 2.80, "unit": "1 pack"},
        {"item": "Ciabatta Bread (Gluten-Free if needed)", "estimated_cost": 2.50, "unit": "1 loaf"},
        {"item": "Pesto Sauce & Fresh Mozzarella", "estimated_cost": 4.50, "unit": "1 tub/ball"},
        {"item": "Ripe Tomatoes & Fresh Basil", "estimated_cost": 2.00, "unit": "1 bag"},
        {"item": "Beef Stew Meat" if not veg else "Dry Brown Lentils", "estimated_cost": 3.00 if veg else 7.50, "unit": "1 lb"},
        {"item": "Carrots, Potatoes, Onions, Celery", "estimated_cost": 3.50, "unit": "1 bundle"}
    ]
    
    subs = [
        {"original": "Beef Stew Meat", "substitute": "Portobello Mushrooms / Brown Lentils", "reason": "Creates an earthy, rich vegetarian stew that is cheaper and cooks faster."},
        {"original": "Ciabatta Bread", "substitute": "Sourdough or Gluten-Free Bread", "reason": "Easier digestion and meets gluten-free dietary needs."},
        {"original": "Mozzarella", "substitute": "Vegan Cashew Cheese", "reason": "Plant-based alternative."}
    ]
    
    todos = [
        {"task_name": "Shop for groceries (pancake mix, eggs, mozzarella, bread, tomatoes, stew ingredients)", "category": "grocery"},
        {"task_name": "Chop stew vegetables (carrots, onions, celery, potatoes, garlic)", "category": "prep"},
        {"task_name": "Slice tomatoes and mozzarella cheese; pluck basil leaves", "category": "prep"},
        {"task_name": "Whisk pancake batter, cook pancakes on griddle, scramble eggs", "category": "cooking"},
        {"task_name": "Assemble panini (pesto, mozzarella, tomatoes, basil) and toast in pan", "category": "cooking"},
        {"task_name": "Sear beef/mushrooms, add chopped vegetables, broth, herbs, simmer low for 60 min", "category": "cooking"}
    ]
    
    return {
        "breakfast": breakfast,
        "lunch": lunch,
        "dinner": dinner,
        "grocery_list": grocery,
        "substitutions": subs,
        "todo_items": todos
    }

if __name__ == '__main__':
    # Get port from environment (important for platforms like Render/Heroku)
    port = int(os.environ.get("PORT", 5000))
    # Run server
    app.run(host='0.0.0.0', port=port, debug=True)
