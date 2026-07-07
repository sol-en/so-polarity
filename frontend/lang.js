const dict = {
    "HOA Accounting - Financial System": {"en": "HOA Accounting - Financial System", "uk": "ЖБК Облік - Фінансова Система"},
    "HOA Accounting": {"en": "HOA Accounting", "uk": "ЖБК Облік"},
    "Dashboard": {"en": "Dashboard", "uk": "Головна"},
    "Transactions": {"en": "Transactions", "uk": "Транзакції"},
    "Charges": {"en": "Billing", "uk": "Нарахування"},
    "Print": {"en": "Reports", "uk": "Друк"},
    "Settings": {"en": "Settings", "uk": "Налаштування"},
    "Administrator": {"en": "Admin", "uk": "Адміністратор"},
    "Toggle theme": {"en": "Toggle theme", "uk": "Перемкнути тему"},
    "Recalculate": {"en": "Recalculate", "uk": "Перерахувати"},
    "Select period...": {"en": "Select period...", "uk": "Оберіть період..."},
    "Last 7 days": {"en": "Last 7 days", "uk": "Останні 7 днів"},
    "Today": {"en": "Today", "uk": "Сьогодні"},
    "Yesterday": {"en": "Yesterday", "uk": "Вчора"},
    "This month": {"en": "This month", "uk": "Поточний місяць"},
    "Last month": {"en": "Last month", "uk": "Минулий місяць"},
    "Month": {"en": "Month", "uk": "Місяць"},
    "Quarter": {"en": "Quarter", "uk": "Квартал"},
    "Year": {"en": "Year", "uk": "Рік"},
    "Period": {"en": "Period", "uk": "Період"},
    "Apply": {"en": "Apply", "uk": "Застосувати"},
    "Cancel": {"en": "Cancel", "uk": "Скасувати"},
    "Loading...": {"en": "Loading...", "uk": "Завантаження..."},
    "Edit": {"en": "Edit", "uk": "Редагувати"},
    "Save": {"en": "Save", "uk": "Зберегти"},
    "Unsaved Changes": {"en": "Unsaved Changes", "uk": "Незбережені зміни"},
    "You have unsaved changes in elevator settings. Save them before leaving?": {"en": "You have unsaved changes in elevator settings. Save them before leaving?", "uk": "У вас є незбережені зміни в налаштуваннях ліфта. Зберегти їх перед переходом?"},
    "is still under development": {"en": "is still under development", "uk": "ще в розробці"},
    "No, discard changes": {"en": "No, discard changes", "uk": "Ні, відмінити зміни"},
    "Yes, save": {"en": "Yes, save", "uk": "Так, зберегти"},
    "Cancel (stay)": {"en": "Cancel (stay)", "uk": "Скасувати (залишитись)"},
    "Initial Balance": {"en": "Beginning Balance", "uk": "Початковий баланс"},
    "Final Balance": {"en": "Ending Balance", "uk": "Кінцевий баланс"},
    "Balance: Actual vs Forecast": {"en": "Balance: Actual vs Forecast", "uk": "Баланс: факт та прогноз"},
    "Details Breakdown": {"en": "Detailed Breakdown", "uk": "Деталізація"},
    "Initiatives Availability": {"en": "Project Funding Availability", "uk": "Доступність ініціатив"},
    "Add Initiative": {"en": "Add Project", "uk": "Додати ініціативу"},
    "Scenario Parameters and Details": {"en": "Scenario Parameters & Details", "uk": "Параметри та деталізація сценарію"},
    "Current Balance": {"en": "Current Balance", "uk": "Поточний баланс"},
    "Tariff (₴/m²)": {"en": "Maintenance Rate (₴/m²)", "uk": "Тариф (₴/м²)"},
    "Expected Collection": {"en": "Expected Collection", "uk": "Очікуваний збір"},
    "Update": {"en": "Update", "uk": "Оновити"},
    "Debtors (Top 10)": {"en": "Top Delinquencies", "uk": "Боржники (ТОП-10)"},
    "Expenses: Breakdown": {"en": "Expense Breakdown", "uk": "Витрати: розбивка"},
    "Apartment": {"en": "Unit", "uk": "Квартира"},
    "Owner": {"en": "Owner", "uk": "Власник"},
    "Debt": {"en": "Balance Due", "uk": "Борг"},
    "Group": {"en": "Category", "uk": "Група"},
    "Amount": {"en": "Amount", "uk": "Сума"},
    "Total": {"en": "Total", "uk": "Всього"},
    "Other": {"en": "Other", "uk": "Решта"},
    "Type": {"en": "Type", "uk": "Тип"},
    "Purpose": {"en": "Description", "uk": "Призначення"},
    "Dashboard error": {"en": "Dashboard error", "uk": "Помилка дашборду"},
    "Inflows": {"en": "Income", "uk": "Надходження"},
    "Expenses": {"en": "Expenses", "uk": "Витрати"},
    "Balance": {"en": "Balance", "uk": "Баланс"},
    "Details": {"en": "Details", "uk": "Деталі"},
    "Parameters": {"en": "Parameters", "uk": "Параметри"},
};


window.currentLang = localStorage.getItem('zhbk_lang') || 'uk';

window.t = function(key) {
    if(dict[key] && dict[key][window.currentLang]) {
        return dict[key][window.currentLang];
    }
    return key;
};

window.toggleLang = function() {
    window.currentLang = window.currentLang === 'uk' ? 'en' : 'uk';
    localStorage.setItem('zhbk_lang', window.currentLang);
    location.reload();
};

document.addEventListener('DOMContentLoaded', () => {
    // Add language toggle button to header
    const headerActions = document.querySelector('.header-actions');
    if (headerActions) {
        const langBtn = document.createElement('button');
        langBtn.className = 'btn btn-secondary';
        langBtn.style.marginRight = '10px';
        langBtn.innerHTML = window.currentLang === 'uk' ? '🇬🇧 EN' : '🇺🇦 UK';
        langBtn.title = "Перемкнути мову / Toggle language";
        langBtn.onclick = window.toggleLang;
        headerActions.prepend(langBtn);
    }
    
    // Auto translate text nodes in DOM that exactly match dictionary keys
    function walkTextNodes(node) {
        if (node.nodeType === 3) {
            let text = node.nodeValue.trim();
            if (dict[text]) {
                node.nodeValue = node.nodeValue.replace(text, window.t(text));
            }
        } else if (node.nodeType === 1 && node.nodeName !== 'SCRIPT' && node.nodeName !== 'STYLE') {
            for (let child of node.childNodes) {
                walkTextNodes(child);
            }
        }
    }
    walkTextNodes(document.body);
});
