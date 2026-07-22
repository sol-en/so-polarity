import re

replacements = {
    "HOA Accounting - Financial System": "ЖБК Облік - Фінансова Система",
    "HOA Accounting": "ЖБК Облік",
    "Dashboard": "Головна",
    "Transactions": "Транзакції",
    "Charges": "Нарахування",
    "Print": "Друк",
    "Settings": "Налаштування",
    "Administrator": "Адміністратор",
    "Toggle theme": "Перемкнути тему",
    "Recalculate": "Перерахувати",
    "Select period...": "Оберіть період...",
    "Last 7 days": "Останні 7 днів",
    "Today": "Сьогодні",
    "Yesterday": "Вчора",
    "This month": "Поточний місяць",
    "Last month": "Минулий місяць",
    "Month": "Місяць",
    "Quarter": "Квартал",
    "Year": "Рік",
    "Period": "Період",
    "Apply": "Застосувати",
    "Cancel": "Скасувати",
    "Loading...": "Завантаження...",
    "Edit": "Редагувати",
    "Save": "Зберегти",
    "Unsaved Changes": "Незбережені зміни",
    "You have unsaved changes in elevator settings. Save them before leaving?": "У вас є незбережені зміни в налаштуваннях ліфта. Зберегти їх перед переходом?",
    "is still under development": "ще в розробці",
    "No, discard changes": "Ні, відмінити зміни",
    "Yes, save": "Так, зберегти",
    "Cancel (stay)": "Скасувати (залишитись)",
    "Initial Balance": "Початковий баланс",
    "Final Balance": "Кінцевий баланс",
    "Balance: Actual vs Forecast": "Баланс: факт та прогноз",
    "Details Breakdown": "Деталізація",
    "Initiatives Availability": "Доступність ініціатив",
    "Add Initiative": "Додати ініціативу",
    "Scenario Parameters and Details": "Параметри та деталізація сценарію",
    "Current Balance": "Поточний баланс",
    "Tariff (₴/m²)": "Тариф (₴/м²)",
    "Expected Collection": "Очікуваний збір",
    "Update": "Оновити",
    "Debtors (Top 10)": "Боржники (ТОП-10)",
    "Expenses: Breakdown": "Витрати: розбивка",
    "Apartment": "Квартира",
    "Owner": "Власник",
    "Debt": "Борг",
    "Group": "Група",
    "Amount": "Сума",
    "Total": "Всього",
    "Other": "Решта",
    "Type": "Тип",
    "Purpose": "Призначення",
    "Dashboard error": "Помилка дашборду",
    "Inflows": "Надходження",
    "Expenses": "Витрати",
    "Balance": "Баланс",
    "Details": "Деталі",
    "Parameters": "Параметри"
}

# Generate lang.js
dict_str = "const dict = {\n"
for en, uk in replacements.items():
    dict_str += f'    "{en}": {{"en": "{en}", "uk": "{uk}"}},\n'
dict_str += "};\n\n"
dict_str += """
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
"""

with open('frontend/lang.js', 'w', encoding='utf-8') as f:
    f.write(dict_str)

print("Created lang.js")
