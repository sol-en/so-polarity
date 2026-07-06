# Polarity - HOA Accounting & Reconciliation System / ЖБК Accounting & Reconciliation System

This system is designed to automate accounting, tariff billing, and bank reconciliation for Housing Cooperatives (HOA).
Ця система розроблена для автоматизації бухгалтерського обліку, нарахувань за тарифами та звірки банківських платежів (реконсиляції) для житлово-будівельних кооперативів (ЖБК).

## Key Features 🚀 / Основні можливості 🚀

1. **Bank Statement Import (PrivatBank) / Імпорт банківських виписок (ПриватБанк)**
   - Download CSV registries and statements. / Завантаження CSV-реєстрів та виписок.
   - Smart deduplication algorithm. / Розумний алгоритм дедублікації.
   - Separation of salaries, taxes, commissions, and incomes. / Відокремлення зарплат, податків, комісій та надходжень.

2. **Automatic and Manual Reconciliation (Matching) / Автоматична та ручна звірка (Метчінг)**
   - Automatic recognition of payments by Name, Address, or Comment. / Автоматичне розпізнавання платежів за ПІБ, адресою або коментарем.
   - System learning: ability to manually link "unrecognized" transactions to contractors or apartments. / Навчання системи: можливість ручної прив'язки "нерозпізнаних" транзакцій до контрагентів або квартир.

3. **Accurate Billing / Точні нарахування (Білінг)**
   - Dynamic tariffs: Operational expenses, Gas, Elevator. / Динамічні тарифи: Експлуатаційні витрати, Газ, Ліфт.
   - Mathematically accurate accruals rounded to 2 decimal places. / Математично точні нарахування: кожна стаття витрат заокруглюється до 2 знаків.
   - Manual adjustment log. / Журнал ручних коригувань.

4. **Analytics and Dashboard / Аналітика та Дашборд**
   - Convenient overview of initial balance, final balance, inflows, and expenses. / Зручний перегляд початкового балансу, кінцевого балансу, надходжень та витрат за будь-який обраний період.
   - Drill-down by groups and types of expenses/incomes. / Деталізація по групах та типах витрат/доходів.

## Tech Stack 🛠 / Технологічний стек 🛠

- **Backend:** Python, FastAPI, SQLAlchemy
- **Database:** SQLite (`zhbk_app.db`)
- **Frontend:** Vanilla JS, HTML, CSS
- **Integrations:** Gmail API

## How to run locally 💻 / Як запустити локально 💻

1. **Install dependencies / Встановіть залежності:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start FastAPI server / Запустіть сервер FastAPI:**
   ```bash
   uvicorn backend.main:app --reload
   ```

3. **Open in browser / Відкрийте у браузері:**
   `http://127.0.0.1:8000`

## Project Structure 📂 / Структура проекту 📂
- `/backend` - Server logic (routes, parsers, matching algorithms). / Логіка сервера.
- `/frontend` - User interface (HTML, CSS, JS). / Інтерфейс користувача.
- `zhbk_app.db` - Local database. / Локальна база даних.
