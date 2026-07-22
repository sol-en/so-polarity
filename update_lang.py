# -*- coding: utf-8 -*-
dict_map = {
    "ЖБК Облік - Фінансова Система": "HOA Accounting - Financial System",
    "ЖБК Облік": "HOA Accounting",
    "Головна": "Dashboard",
    "Транзакції": "Transactions",
    "Нарахування": "Billing",
    "Друк": "Reports",
    "Налаштування": "Settings",
    "Адміністратор": "Admin",
    "Перемкнути тему": "Toggle theme",
    "Перерахувати": "Recalculate",
    "Оберіть період...": "Select period...",
    "Останні 7 днів": "Last 7 days",
    "Сьогодні": "Today",
    "Вчора": "Yesterday",
    "Поточний місяць": "This month",
    "Минулий місяць": "Last month",
    "Місяць": "Month",
    "Квартал": "Quarter",
    "Рік": "Year",
    "Період": "Period",
    "Застосувати": "Apply",
    "Скасувати": "Cancel",
    "Завантаження...": "Loading...",
    "Редагувати": "Edit",
    "Зберегти": "Save",
    "Незбережені зміни": "Unsaved Changes",
    "У вас є незбережені зміни в налаштуваннях ліфта. Зберегти їх перед переходом?": "You have unsaved changes in elevator settings. Save them before leaving?",
    "ще в розробці": "is still under development",
    "Ні, відмінити зміни": "No, discard changes",
    "Так, зберегти": "Yes, save",
    "Скасувати (залишитись)": "Cancel (stay)",
    "Початковий баланс": "Beginning Balance",
    "Кінцевий баланс": "Ending Balance",
    "Баланс: факт та прогноз": "Balance: Actual vs Forecast",
    "Деталізація": "Detailed Breakdown",
    "Доступність ініціатив": "Project Funding Availability",
    "Додати ініціативу": "Add Project",
    "Параметри та деталізація сценарію": "Scenario Parameters & Details",
    "Поточний баланс": "Current Balance",
    "Тариф (₴/м²)": "Maintenance Rate (₴/m²)",
    "Очікуваний збір": "Expected Collection",
    "Оновити": "Update",
    "Боржники (ТОП-10)": "Top Delinquencies",
    "Витрати: розбивка": "Expense Breakdown",
    "Квартира": "Unit",
    "Власник": "Owner",
    "Борг": "Balance Due",
    "Група": "Category",
    "Сума": "Amount",
    "Всього": "Total",
    "Решта": "Other",
    "Тип": "Type",
    "Призначення": "Description",
    "Помилка дашборду": "Dashboard error",
    "Надходження": "Income",
    "Витрати": "Expenses",
    "Баланс на кінець періоду": "Ending Balance",
    "Баланс": "Balance",
    "Деталі": "Details",
    "Параметри": "Parameters",
    "Факт (баланс)": "Actual (Balance)",
    "Сценарій": "Scenario",
    "Січ": "Jan", "Лют": "Feb", "Бер": "Mar", "Квіт": "Apr", "Трав": "May", "Черв": "Jun", "Лип": "Jul", "Серп": "Aug", "Вер": "Sep", "Жовт": "Oct", "Лист": "Nov", "Груд": "Dec",
    "січ": "Jan", "лют": "Feb", "бер": "Mar", "квіт": "Apr", "трав": "May", "черв": "Jun", "лип": "Jul", "серп": "Aug", "вер": "Sep", "жовт": "Oct", "лист": "Nov", "груд": "Dec",
    "Січень": "January", "Лютий": "February", "Березень": "March", "Квітень": "April", "Травень": "May", "Червень": "June", "Липень": "July", "Серпень": "August", "Вересень": "September", "Жовтень": "October", "Листопад": "November", "Грудень": "December",
    "Ініціатива": "Initiative",
    "Дата старту": "Start Date",
    "Вартість": "Amount",
    "Дії": "Actions",
    "грн": "UAH"
}

js_content = "const dict = {\n"
for uk, en in dict_map.items():
    # We use the Ukrainian string as the key!
    js_content += f'    "{uk}": {{"en": "{en}", "uk": "{uk}"}},\n'
js_content += "};\n\n"

js_content += """
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
        langBtn.title = window.currentLang === 'uk' ? 'Switch to English' : 'Перемкнути на Українську';
        langBtn.onclick = window.toggleLang;
        headerActions.prepend(langBtn);
    }
    
    const dictEntries = Object.entries(dict).sort((a, b) => b[0].length - a[0].length);

    function translateNode(node) {
        if (node.nodeType === 3) {
            let originalText = node.nodeValue;
            if (!originalText.trim()) return;
            let newText = originalText;
            for (let [ukStr, translations] of dictEntries) {
                if (newText.includes(ukStr)) {
                    newText = newText.split(ukStr).join(translations[window.currentLang]);
                }
            }
            if (newText !== originalText) {
                node.nodeValue = newText;
            }
        } else if (node.nodeType === 1 && node.nodeName !== 'SCRIPT' && node.nodeName !== 'STYLE') {
            if (node.placeholder) {
                let pText = node.placeholder;
                let originalPText = pText;
                for (let [ukStr, translations] of dictEntries) {
                    if (pText.includes(ukStr)) {
                        pText = pText.split(ukStr).join(translations[window.currentLang]);
                    }
                }
                if (pText !== originalPText) node.placeholder = pText;
            }
            node.childNodes.forEach(translateNode);
        }
    }
    
    // Always translate on load based on currentLang
    translateNode(document.body);
    
    const observer = new MutationObserver(mutations => {
        mutations.forEach(mutation => {
            mutation.addedNodes.forEach(addedNode => {
                translateNode(addedNode);
            });
            if (mutation.type === 'characterData') {
                // Prevent infinite loop by checking if it already changed
                let originalText = mutation.target.nodeValue;
                if (!originalText.trim()) return;
                let newText = originalText;
                for (let [ukStr, translations] of dictEntries) {
                    if (newText.includes(ukStr)) {
                        newText = newText.split(ukStr).join(translations[window.currentLang]);
                    }
                }
                if (newText !== originalText) {
                    mutation.target.nodeValue = newText;
                }
            }
        });
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
});
"""
with open('frontend/lang.js', 'w', encoding='utf-8') as f:
    f.write(js_content)
