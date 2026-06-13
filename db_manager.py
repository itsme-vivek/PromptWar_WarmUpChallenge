import sqlite3
import os
import json

DATABASE_FILE = "cooking_app.db"

def get_db_connection():
    """Create a new database connection."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Settings Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        api_key TEXT,
        dietary_preferences TEXT,
        budget_default REAL
    )
    """)
    
    # Meal Plans Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meal_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day_description TEXT,
        breakfast TEXT,
        lunch TEXT,
        dinner TEXT,
        grocery_list TEXT, -- JSON representation of grocery list
        substitutions TEXT, -- JSON representation of substitutions
        budget_target REAL,
        budget_estimated REAL,
        budget_status TEXT, -- 'under', 'within', 'over'
        budget_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Todos/Checklist Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS todos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meal_plan_id INTEGER,
        task_name TEXT,
        category TEXT, -- 'grocery', 'prep', 'cooking', 'custom'
        is_completed INTEGER DEFAULT 0,
        FOREIGN KEY (meal_plan_id) REFERENCES meal_plans(id) ON DELETE CASCADE
    )
    """)
    
    # Seed default settings if not exists
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO settings (api_key, dietary_preferences, budget_default) VALUES (?, ?, ?)", ("", "none", 25.0))
        
    conn.commit()
    conn.close()

def get_settings():
    """Retrieve settings."""
    conn = get_db_connection()
    row = conn.execute("SELECT api_key, dietary_preferences, budget_default FROM settings WHERE id = 1").fetchone()
    conn.close()
    if row:
        return {
            "api_key": row["api_key"],
            "dietary_preferences": row["dietary_preferences"],
            "budget_default": row["budget_default"]
        }
    return {"api_key": "", "dietary_preferences": "none", "budget_default": 25.0}

def save_settings(api_key, dietary_preferences, budget_default):
    """Save user settings."""
    conn = get_db_connection()
    conn.execute(
        "UPDATE settings SET api_key = ?, dietary_preferences = ?, budget_default = ? WHERE id = 1",
        (api_key, dietary_preferences, budget_default)
    )
    conn.commit()
    conn.close()

def save_meal_plan(day_description, breakfast, lunch, dinner, grocery_list, substitutions, budget_target, budget_estimated, budget_status, budget_notes, todo_items):
    """Save a generated meal plan and all associated checklist items.
    
    grocery_list and substitutions should be standard Python structures (lists/dicts) and will be serialized.
    todo_items should be a list of dicts: [{'task_name': '...', 'category': '...'}]
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Insert Meal Plan
        cursor.execute("""
        INSERT INTO meal_plans (
            day_description, breakfast, lunch, dinner, grocery_list, substitutions, budget_target, budget_estimated, budget_status, budget_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            day_description,
            breakfast,
            lunch,
            dinner,
            json.dumps(grocery_list),
            json.dumps(substitutions),
            budget_target,
            budget_estimated,
            budget_status,
            budget_notes
        ))
        
        meal_plan_id = cursor.lastrowid
        
        # Insert Todos
        for item in todo_items:
            cursor.execute(
                "INSERT INTO todos (meal_plan_id, task_name, category, is_completed) VALUES (?, ?, ?, 0)",
                (meal_plan_id, item["task_name"], item["category"])
            )
            
        conn.commit()
        return meal_plan_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_meal_plans():
    """Retrieve all saved meal plans summary, including tasks completion status."""
    conn = get_db_connection()
    # Join with todos to count completed/total tasks
    query = """
    SELECT 
        m.id, 
        m.day_description, 
        m.created_at, 
        m.budget_target,
        m.budget_estimated,
        m.budget_status,
        COUNT(t.id) as total_tasks,
        SUM(CASE WHEN t.is_completed = 1 THEN 1 ELSE 0 END) as completed_tasks
    FROM meal_plans m
    LEFT JOIN todos t ON m.id = t.meal_plan_id
    GROUP BY m.id
    ORDER BY m.created_at DESC
    """
    rows = conn.execute(query).fetchall()
    conn.close()
    
    plans = []
    for r in rows:
        plans.append({
            "id": r["id"],
            "day_description": r["day_description"],
            "created_at": r["created_at"],
            "budget_target": r["budget_target"],
            "budget_estimated": r["budget_estimated"],
            "budget_status": r["budget_status"],
            "total_tasks": r["total_tasks"],
            "completed_tasks": r["completed_tasks"] or 0
        })
    return plans

def get_meal_plan_details(plan_id):
    """Retrieve full details of a specific meal plan and its checklist."""
    conn = get_db_connection()
    plan_row = conn.execute("SELECT * FROM meal_plans WHERE id = ?", (plan_id,)).fetchone()
    if not plan_row:
        conn.close()
        return None
        
    todo_rows = conn.execute("SELECT id, task_name, category, is_completed FROM todos WHERE meal_plan_id = ?", (plan_id,)).fetchall()
    conn.close()
    
    todos = []
    for t in todo_rows:
        todos.append({
            "id": t["id"],
            "task_name": t["task_name"],
            "category": t["category"],
            "is_completed": bool(t["is_completed"])
        })
        
    return {
        "id": plan_row["id"],
        "day_description": plan_row["day_description"],
        "breakfast": plan_row["breakfast"],
        "lunch": plan_row["lunch"],
        "dinner": plan_row["dinner"],
        "grocery_list": json.loads(plan_row["grocery_list"]),
        "substitutions": json.loads(plan_row["substitutions"]),
        "budget_target": plan_row["budget_target"],
        "budget_estimated": plan_row["budget_estimated"],
        "budget_status": plan_row["budget_status"],
        "budget_notes": plan_row["budget_notes"],
        "created_at": plan_row["created_at"],
        "todos": todos
    }

def toggle_todo(todo_id, is_completed):
    """Toggle the completed status of a checklist item."""
    conn = get_db_connection()
    conn.execute("UPDATE todos SET is_completed = ? WHERE id = ?", (1 if is_completed else 0, todo_id))
    conn.commit()
    conn.close()

def add_custom_todo(plan_id, task_name, category="custom"):
    """Add a custom checklist item."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO todos (meal_plan_id, task_name, category, is_completed) VALUES (?, ?, ?, 0)",
        (plan_id, task_name, category)
    )
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {
        "id": new_id,
        "task_name": task_name,
        "category": category,
        "is_completed": False
    }

def delete_todo(todo_id):
    """Delete a specific checklist item."""
    conn = get_db_connection()
    conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    conn.commit()
    conn.close()

def delete_meal_plan(plan_id):
    """Delete a meal plan and all cascade todos."""
    conn = get_db_connection()
    # sqlite3 requires enabling foreign keys to cascade automatically, or we delete manually:
    conn.execute("DELETE FROM todos WHERE meal_plan_id = ?", (plan_id,))
    conn.execute("DELETE FROM meal_plans WHERE id = ?", (plan_id,))
    conn.commit()
    conn.close()
