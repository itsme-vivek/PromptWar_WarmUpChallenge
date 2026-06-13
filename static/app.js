/* ==========================================================================
   CookFlow AI - App Controller
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    // State Variables
    let currentPlan = null;
    let settings = { api_key: '', dietary_preferences: 'none', budget_default: 25.0 };

    // DOM Elements - Sidebar
    const dayDescriptionInput = document.getElementById('dayDescription');
    const dietaryPrefSelect = document.getElementById('dietaryPref');
    const budgetLimitSlider = document.getElementById('budgetLimit');
    const budgetValueLabel = document.getElementById('budgetValue');
    const btnGenerate = document.getElementById('btnGenerate');
    const templateButtons = document.querySelectorAll('.btn-template');

    // DOM Elements - Headers & Badges
    const currentPlanTitle = document.getElementById('currentPlanTitle');
    const currentPlanMeta = document.getElementById('currentPlanMeta');
    const apiStatusBadge = document.getElementById('apiStatusBadge');
    const statusText = document.getElementById('statusText');

    // DOM Elements - Tabs
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');

    // DOM Elements - Checklist Tab
    const progressPercent = document.getElementById('progressPercent');
    const progressBarFill = document.getElementById('progressBarFill');
    const checklistEmptyState = document.getElementById('checklistEmptyState');
    const todoCategoriesContainer = document.getElementById('todoCategoriesContainer');
    const listGrocery = document.getElementById('list-grocery');
    const listPrep = document.getElementById('list-prep');
    const listCooking = document.getElementById('list-cooking');
    const listCustom = document.getElementById('list-custom');
    const customTaskInput = document.getElementById('customTaskInput');
    const btnAddCustom = document.getElementById('btnAddCustom');

    // DOM Elements - Meal Plan & Budget Tab
    const mealPlanEmptyState = document.getElementById('mealPlanEmptyState');
    const mealPlanGridContainer = document.getElementById('mealPlanGridContainer');
    const mealBreakfastTitle = document.getElementById('mealBreakfastTitle');
    const mealLunchTitle = document.getElementById('mealLunchTitle');
    const mealDinnerTitle = document.getElementById('mealDinnerTitle');
    const budgetFeasibilityBadge = document.getElementById('budgetFeasibilityBadge');
    const budgetGaugeTarget = document.getElementById('budgetGaugeTarget');
    const budgetGaugeEstimated = document.getElementById('budgetGaugeEstimated');
    const budgetComparisonFill = document.getElementById('budgetComparisonFill');
    const budgetNotesText = document.getElementById('budgetNotesText');
    const subsTableBody = document.getElementById('subsTableBody');

    // DOM Elements - History Tab
    const historyEmptyState = document.getElementById('historyEmptyState');
    const historyListContainer = document.getElementById('historyListContainer');

    // DOM Elements - Settings Modal
    const btnSettings = document.getElementById('btnSettings');
    const settingsModal = document.getElementById('settingsModal');
    const btnCloseSettings = document.getElementById('btnCloseSettings');
    const btnCancelSettings = document.getElementById('btnCancelSettings');
    const btnSaveSettings = document.getElementById('btnSaveSettings');
    const settingsApiKey = document.getElementById('settingsApiKey');
    const settingsDietary = document.getElementById('settingsDietary');
    const settingsBudget = document.getElementById('settingsBudget');
    const btnToggleApiKeyVisibility = document.getElementById('btnToggleApiKeyVisibility');

    const toastContainer = document.getElementById('toastContainer');

    /* ==========================================================================
       Initialization
       ========================================================================== */
    init();

    async function init() {
        // Budget slider sync
        budgetLimitSlider.addEventListener('input', (e) => {
            budgetValueLabel.textContent = `$${e.target.value}`;
        });

        // Load Settings
        await loadSettings();

        // Load History
        await loadHistory();

        // Load Latest Saved Plan (if any)
        loadLatestPlan();

        // Setup Event Listeners
        setupEventListeners();
    }

    /* ==========================================================================
       API Requests & State Loaders
       ========================================================================== */
    async function loadSettings() {
        try {
            const res = await fetch('/api/settings');
            if (res.ok) {
                settings = await res.json();
                
                // Populate forms
                dietaryPrefSelect.value = settings.dietary_preferences;
                budgetLimitSlider.value = settings.budget_default;
                budgetValueLabel.textContent = `$${settings.budget_default}`;

                settingsApiKey.value = settings.api_key;
                settingsDietary.value = settings.dietary_preferences;
                settingsBudget.value = settings.budget_default;

                updateApiBadge();
            }
        } catch (e) {
            showToast('Failed to load settings', 'error');
        }
    }

    function updateApiBadge() {
        if (settings.api_key && settings.api_key.trim().length > 0) {
            apiStatusBadge.className = 'api-status-badge live';
            statusText.textContent = 'AI Mode Active';
        } else {
            apiStatusBadge.className = 'api-status-badge mock';
            statusText.textContent = 'Demo Mode';
        }
    }

    async function saveSettings() {
        const apiKey = settingsApiKey.value.trim();
        const dietary = settingsDietary.value;
        const budget = parseFloat(settingsBudget.value) || 25.0;

        try {
            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_key: apiKey,
                    dietary_preferences: dietary,
                    budget_default: budget
                })
            });

            if (res.ok) {
                settings = { api_key: apiKey, dietary_preferences: dietary, budget_default: budget };
                
                // Sync sidebar views
                dietaryPrefSelect.value = dietary;
                budgetLimitSlider.value = budget;
                budgetValueLabel.textContent = `$${budget}`;

                updateApiBadge();
                settingsModal.classList.add('hidden');
                showToast('Settings saved successfully', 'success');
            } else {
                showToast('Failed to save settings', 'error');
            }
        } catch (e) {
            showToast('Network error saving settings', 'error');
        }
    }

    async function loadHistory() {
        try {
            const res = await fetch('/api/meal-plans');
            if (res.ok) {
                const plans = await res.json();
                renderHistory(plans);
            }
        } catch (e) {
            showToast('Failed to load meal plan history', 'error');
        }
    }

    async function loadLatestPlan() {
        try {
            const res = await fetch('/api/meal-plans');
            if (res.ok) {
                const plans = await res.json();
                if (plans && plans.length > 0) {
                    // Load the first (newest) one
                    loadPlanDetails(plans[0].id, false);
                }
            }
        } catch (e) {
            console.error('Error auto-loading latest plan', e);
        }
    }

    async function loadPlanDetails(planId, switchTab = true) {
        try {
            const res = await fetch(`/api/meal-plans/${planId}`);
            if (res.ok) {
                currentPlan = await res.json();
                renderPlan(currentPlan);
                if (switchTab) {
                    switchTabTo('checklist');
                    showToast('Meal plan loaded successfully', 'info');
                }
            } else {
                showToast('Failed to load plan details', 'error');
            }
        } catch (e) {
            showToast('Network error loading plan details', 'error');
        }
    }

    async function deletePlan(planId, event) {
        if (event) event.stopPropagation();
        if (!confirm('Are you sure you want to delete this meal plan and its checklist?')) return;

        try {
            const res = await fetch(`/api/meal-plans/${planId}`, { method: 'DELETE' });
            if (res.ok) {
                showToast('Meal plan deleted', 'info');
                await loadHistory();
                
                // If the currently displayed plan is the deleted one, clear display
                if (currentPlan && currentPlan.id === planId) {
                    currentPlan = null;
                    resetDisplay();
                }
            }
        } catch (e) {
            showToast('Failed to delete meal plan', 'error');
        }
    }

    /* ==========================================================================
       Generation Handler
       ========================================================================== */
    async function handleGenerate() {
        const description = dayDescriptionInput.value.trim();
        const dietary = dietaryPrefSelect.value;
        const budget = parseFloat(budgetLimitSlider.value) || 25.0;

        if (!description) {
            showToast('Please describe your day first!', 'warning');
            dayDescriptionInput.focus();
            return;
        }

        // Set Loading state
        btnGenerate.disabled = true;
        btnGenerate.querySelector('.btn-text').textContent = 'Generating...';
        btnGenerate.querySelector('.spinner').classList.remove('hidden');

        try {
            const res = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    day_description: description,
                    dietary_preferences: dietary,
                    budget: budget
                })
            });

            if (res.ok) {
                currentPlan = await res.json();
                
                // Render and navigate
                renderPlan(currentPlan);
                switchTabTo('checklist');
                
                // Clear input
                dayDescriptionInput.value = '';

                // Refresh history
                await loadHistory();

                if (currentPlan.is_mock) {
                    if (settings.api_key) {
                        showToast('Gemini API failed. Generated using local fallback planner!', 'warning');
                    } else {
                        showToast('Plan generated in Demo Mode!', 'success');
                    }
                } else {
                    showToast('AI Plan generated successfully!', 'success');
                }
            } else {
                const errData = await res.json();
                showToast(errData.error || 'Failed to generate plan', 'error');
            }
        } catch (e) {
            showToast('Connection to server failed. Verify app is running.', 'error');
        } finally {
            // Reset Loading state
            btnGenerate.disabled = false;
            btnGenerate.querySelector('.btn-text').textContent = 'Generate CookFlow';
            btnGenerate.querySelector('.spinner').classList.add('hidden');
        }
    }

    /* ==========================================================================
       Checklist Toggling & Actions
       ========================================================================== */
    async function toggleTodo(todoId, checkbox) {
        const isCompleted = checkbox.checked;
        try {
            const res = await fetch('/api/todos/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    todo_id: todoId,
                    is_completed: isCompleted
                })
            });

            if (res.ok) {
                // Update local model
                const todoItem = currentPlan.todos.find(t => t.id === todoId);
                if (todoItem) {
                    todoItem.is_completed = isCompleted;
                }
                
                // Update progress bar
                updateProgress();

                // Check if 100% completed
                checkAllCompleted();

                // Refresh history metrics in background
                loadHistory();
            } else {
                checkbox.checked = !isCompleted; // rollback
                showToast('Failed to update task state', 'error');
            }
        } catch (e) {
            checkbox.checked = !isCompleted; // rollback
            showToast('Network error toggling task', 'error');
        }
    }

    async function handleAddCustomTask() {
        const text = customTaskInput.value.trim();
        if (!text || !currentPlan) return;

        try {
            const res = await fetch('/api/todos/custom', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    plan_id: currentPlan.id,
                    task_name: text,
                    category: 'custom'
                })
            });

            if (res.ok) {
                const newTodo = await res.json();
                currentPlan.todos.push(newTodo);
                
                // Append directly to list
                const li = createTodoLi(newTodo);
                listCustom.appendChild(li);
                
                customTaskInput.value = '';
                updateProgress();
                showToast('Custom task added', 'success');

                // Refresh history metrics
                loadHistory();
            }
        } catch (e) {
            showToast('Failed to add custom task', 'error');
        }
    }

    async function deleteTodoItem(todoId, liElement) {
        try {
            const res = await fetch(`/api/todos/${todoId}`, { method: 'DELETE' });
            if (res.ok) {
                // Remove from local list
                currentPlan.todos = currentPlan.todos.filter(t => t.id !== todoId);
                
                // Remove from DOM
                const parentUl = liElement.parentNode;
                liElement.remove();
                
                // If the list is now empty, add the empty warning message
                if (parentUl && parentUl.children.length === 0) {
                    let msg = '🛒 No grocery items generated';
                    if (parentUl.id === 'list-prep') msg = '🔪 No meal prep items generated';
                    if (parentUl.id === 'list-cooking') msg = '🔥 No cooking items generated';
                    if (parentUl.id === 'list-custom') msg = '✨ No custom items added';
                    checkEmptyCategory(parentUl, msg);
                }
                
                // Recalculate progress
                updateProgress();
                showToast('Task removed', 'info');
                
                // Refresh history metrics
                loadHistory();
            } else {
                showToast('Failed to delete task', 'error');
            }
        } catch (e) {
            showToast('Network error deleting task', 'error');
        }
    }

    /* ==========================================================================
       Rendering Methods
       ========================================================================== */
    function renderPlan(plan) {
        if (!plan) {
            resetDisplay();
            return;
        }

        // Title and Meta
        currentPlanTitle.textContent = `Schedule: ${plan.created_at.slice(0, 10)}`;
        // Snippet of description
        const descSnippet = plan.day_description.length > 50 ? plan.day_description.slice(0, 50) + '...' : plan.day_description;
        currentPlanMeta.textContent = `Day Vibe: "${descSnippet}" | Target: $${plan.budget_target.toFixed(2)}`;

        // Toggle visibility
        checklistEmptyState.classList.add('hidden');
        todoCategoriesContainer.classList.remove('hidden');

        mealPlanEmptyState.classList.add('hidden');
        mealPlanGridContainer.classList.remove('hidden');

        // Render Meals
        mealBreakfastTitle.textContent = plan.breakfast;
        mealLunchTitle.textContent = plan.lunch;
        mealDinnerTitle.textContent = plan.dinner;

        // Render Budget Metrics
        budgetGaugeTarget.textContent = `$${plan.budget_target.toFixed(2)}`;
        budgetGaugeEstimated.textContent = `$${plan.budget_estimated.toFixed(2)}`;
        
        // Feasibility Badge Class
        budgetFeasibilityBadge.textContent = `${plan.budget_status.toUpperCase()}`;
        budgetFeasibilityBadge.className = `budget-badge ${plan.budget_status}`;
        
        // Budget comparison bar fill
        let percent = (plan.budget_estimated / plan.budget_target) * 100;
        percent = Math.min(percent, 100); // capped at 100%
        budgetComparisonFill.style.width = `${percent}%`;
        budgetComparisonFill.className = `comparison-bar-fill ${plan.budget_status}`;

        // Budget Notes
        budgetNotesText.textContent = plan.budget_notes;

        // Render Substitutions
        subsTableBody.innerHTML = '';
        if (plan.substitutions && plan.substitutions.length > 0) {
            plan.substitutions.forEach(s => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${s.original}</td>
                    <td>${s.substitute}</td>
                    <td>${s.reason}</td>
                `;
                subsTableBody.appendChild(tr);
            });
        } else {
            subsTableBody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No substitutions needed for this plan.</td></tr>`;
        }

        // Render Checklist Lists
        listGrocery.innerHTML = '';
        listPrep.innerHTML = '';
        listCooking.innerHTML = '';
        listCustom.innerHTML = '';

        plan.todos.forEach(todo => {
            const li = createTodoLi(todo);
            if (todo.category === 'grocery') {
                listGrocery.appendChild(li);
            } else if (todo.category === 'prep') {
                listPrep.appendChild(li);
            } else if (todo.category === 'cooking') {
                listCooking.appendChild(li);
            } else {
                listCustom.appendChild(li);
            }
        });

        // Add empty category warnings if none
        checkEmptyCategory(listGrocery, '🛒 No grocery items generated');
        checkEmptyCategory(listPrep, '🔪 No meal prep items generated');
        checkEmptyCategory(listCooking, '🔥 No cooking items generated');

        // Update progress bar
        updateProgress();
    }

    function createTodoLi(todo) {
        const li = document.createElement('li');
        li.className = 'todo-item';
        
        const label = document.createElement('label');
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = todo.is_completed;
        checkbox.addEventListener('change', () => toggleTodo(todo.id, checkbox));

        const checkmark = document.createElement('span');
        checkmark.className = 'checkmark';

        const textSpan = document.createElement('span');
        textSpan.className = 'todo-text';
        textSpan.textContent = todo.task_name;

        label.appendChild(checkbox);
        label.appendChild(checkmark);
        label.appendChild(textSpan);
        li.appendChild(label);

        // Delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.className = 'btn-delete-task';
        deleteBtn.title = 'Delete task';
        deleteBtn.innerHTML = '&times;';
        deleteBtn.addEventListener('click', (e) => {
            e.preventDefault();
            deleteTodoItem(todo.id, li);
        });
        li.appendChild(deleteBtn);

        return li;
    }

    function checkEmptyCategory(listElement, message) {
        if (listElement.children.length === 0) {
            const li = document.createElement('li');
            li.style.color = 'var(--text-muted)';
            li.style.fontSize = '13px';
            li.style.padding = '8px';
            li.textContent = message;
            listElement.appendChild(li);
        }
    }

    function updateProgress() {
        if (!currentPlan || !currentPlan.todos || currentPlan.todos.length === 0) {
            progressPercent.textContent = '0%';
            progressBarFill.style.width = '0%';
            return;
        }

        const total = currentPlan.todos.length;
        const completed = currentPlan.todos.filter(t => t.is_completed).length;
        const percent = Math.round((completed / total) * 100);

        progressPercent.textContent = `${percent}%`;
        progressBarFill.style.width = `${percent}%`;
    }

    function checkAllCompleted() {
        const total = currentPlan.todos.length;
        const completed = currentPlan.todos.filter(t => t.is_completed).length;
        if (total > 0 && completed === total) {
            showToast('🎉 Awesome! You completed your entire cooking workflow!', 'success');
        }
    }

    function resetDisplay() {
        currentPlanTitle.textContent = 'Today\'s Cooking Schedule';
        currentPlanMeta.textContent = 'Start by generating an AI meal plan or loading a saved one.';

        checklistEmptyState.classList.remove('hidden');
        todoCategoriesContainer.classList.add('hidden');

        mealPlanEmptyState.classList.remove('hidden');
        mealPlanGridContainer.classList.add('hidden');

        progressPercent.textContent = '0%';
        progressBarFill.style.width = '0%';
    }

    function renderHistory(plans) {
        historyListContainer.innerHTML = '';
        if (plans && plans.length > 0) {
            historyEmptyState.classList.add('hidden');
            plans.forEach(plan => {
                const item = document.createElement('div');
                item.className = 'history-item card';
                
                // Calculate completion percentage
                const completion = plan.total_tasks > 0 ? Math.round((plan.completed_tasks / plan.total_tasks) * 100) : 0;
                
                // Format description snippet
                const desc = plan.day_description.length > 65 ? plan.day_description.slice(0, 65) + '...' : plan.day_description;
                // Format date nicely
                const date = new Date(plan.created_at).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                });

                item.innerHTML = `
                    <div class="history-info">
                        <span class="history-date">${date}</span>
                        <span class="history-desc">"${desc}"</span>
                        <div class="history-meta-row">
                            <span>Cost: <strong>$${plan.budget_estimated.toFixed(2)}</strong></span>
                            <span>Budget Limit: $${plan.budget_target.toFixed(2)}</span>
                            <span>Progress: <strong>${completion}%</strong> (${plan.completed_tasks}/${plan.total_tasks} tasks)</span>
                        </div>
                    </div>
                    <div class="history-actions">
                        <button type="button" class="btn-sec btn-load-plan" style="padding: 6px 12px; font-size: 12px;">Load</button>
                        <button type="button" class="btn-icon btn-delete-plan" title="Delete Plan" style="width: 32px; height: 32px;">
                            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                            </svg>
                        </button>
                    </div>
                `;

                // Add actions
                item.querySelector('.btn-load-plan').addEventListener('click', () => loadPlanDetails(plan.id));
                item.querySelector('.btn-delete-plan').addEventListener('click', (e) => deletePlan(plan.id, e));

                historyListContainer.appendChild(item);
            });
        } else {
            historyEmptyState.classList.remove('hidden');
        }
    }

    /* ==========================================================================
       Tab Navigation Logic
       ========================================================================== */
    function switchTabTo(tabName) {
        tabButtons.forEach(btn => {
            if (btn.getAttribute('data-tab') === tabName) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        tabPanels.forEach(panel => {
            if (panel.id === `panel-${tabName}`) {
                panel.classList.add('active');
            } else {
                panel.classList.remove('active');
            }
        });
    }

    /* ==========================================================================
       Template Injection Logic
       ========================================================================== */
    function applyTemplate(type) {
        let desc = '';
        let dietary = 'none';
        let budget = 25;

        switch (type) {
            case 'busy':
                desc = "Extremely busy day ahead with work meetings and emails all day. I need a quick 2-minute breakfast, a simple wrap for lunch, and a healthy one-pan dinner that requires almost no cleanup.";
                dietary = 'none';
                budget = 20;
                break;
            case 'fitness':
                desc = "Heavy workout session scheduled for this afternoon. I need nutrient-dense meals, high protein for recovery, healthy carbs, and healthy fats. Make sure my lunch and dinner have good clean protein sources.";
                dietary = 'none';
                budget = 30;
                break;
            case 'budget':
                desc = "I am focusing on saving money. Build me a delicious plan using low-cost pantry staples like rice, beans, pasta, and eggs, but still keep it healthy and satisfying.";
                dietary = 'none';
                budget = 10;
                break;
            case 'relaxed':
                desc = "Cozy day off. I have plenty of time and want to make fluffy pancakes in the morning, a fresh Caprese lunch, and spend an hour simmering a rich, hearty stew for dinner.";
                dietary = 'none';
                budget = 40;
                break;
        }

        // Apply values to UI
        dayDescriptionInput.value = desc;
        dietaryPrefSelect.value = dietary;
        budgetLimitSlider.value = budget;
        budgetValueLabel.textContent = `$${budget}`;

        showToast('Template day loaded! Click Generate to create plan.', 'info');
    }

    /* ==========================================================================
       Toast & Utilities
       ========================================================================== */
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        let icon = 'ℹ️';
        if (type === 'success') icon = '✅';
        if (type === 'warning') icon = '⚠️';
        if (type === 'error') icon = '❌';

        toast.innerHTML = `
            <span>${icon} ${message}</span>
            <button class="toast-close">&times;</button>
        `;

        toast.querySelector('.toast-close').addEventListener('click', () => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        });

        toastContainer.appendChild(toast);

        // Auto remove after 4.5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }
        }, 4500);
    }

    /* ==========================================================================
       Event Listeners Wiring
       ========================================================================== */
    function setupEventListeners() {
        // Tab clicks
        tabButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const tab = btn.getAttribute('data-tab');
                switchTabTo(tab);
            });
        });

        // Templates
        templateButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const type = btn.getAttribute('data-template');
                applyTemplate(type);
            });
        });

        // Generate button
        btnGenerate.addEventListener('click', handleGenerate);

        // Custom task adding
        btnAddCustom.addEventListener('click', handleAddCustomTask);
        customTaskInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleAddCustomTask();
        });

        // Settings modal controls
        btnSettings.addEventListener('click', () => {
            // Reload settings to ensure fresh state in form
            settingsApiKey.value = settings.api_key;
            settingsDietary.value = settings.dietary_preferences;
            settingsBudget.value = settings.budget_default;
            settingsModal.classList.remove('hidden');
        });

        btnCloseSettings.addEventListener('click', () => settingsModal.classList.add('hidden'));
        btnCancelSettings.addEventListener('click', () => settingsModal.classList.add('hidden'));
        btnSaveSettings.addEventListener('click', saveSettings);

        // Close modal when clicking outside card
        settingsModal.addEventListener('click', (e) => {
            if (e.target === settingsModal) {
                settingsModal.classList.add('hidden');
            }
        });

        // API Key visible toggler
        btnToggleApiKeyVisibility.addEventListener('click', () => {
            if (settingsApiKey.type === 'password') {
                settingsApiKey.type = 'text';
                btnToggleApiKeyVisibility.textContent = '🔒';
            } else {
                settingsApiKey.type = 'password';
                btnToggleApiKeyVisibility.textContent = '👁️';
            }
        });
    }
});
