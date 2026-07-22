import re

with open('frontend/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    "Dashboard": "Dashboard",
    "Transactions": "Transactions",
    "Charges": "Charges",
    "Print": "Print",
    "Settings": "Settings",
    "Administrator": "Administrator",
    "Toggle theme": "Toggle theme",
    "Recalculate": "Recalculate",
    "Select period...": "Select period...",
    "Last 7 days": "Last 7 days",
    "Today": "Today",
    "Yesterday": "Yesterday",
    "This month": "This month",
    "Last month": "Last month",
    "Month": "Month",
    "Quarter": "Quarter",
    "Year": "Year",
    "Period": "Period",
    "Apply": "Apply",
    "Cancel": "Cancel",
    "Loading...": "Loading...",
    "Edit": "Edit",
    "Save": "Save",
    "Unsaved Changes": "Unsaved Changes",
    "You have unsaved changes in elevator settings. Save them before leaving?": "You have unsaved changes in elevator settings. Save them before leaving?",
    "is still under development": "is still under development",
    "No, discard changes": "No, discard changes",
    "Yes, save": "Yes, save",
    "Cancel (stay)": "Cancel (stay)",
    "Initial Balance": "Initial Balance",
    "Final Balance": "Final Balance",
    "Balance: Actual vs Forecast": "Balance: Actual vs Forecast",
    "Details Breakdown": "Details Breakdown",
    "Initiatives Availability": "Initiatives Availability",
    "Add Initiative": "Add Initiative",
    "Scenario Parameters and Details": "Scenario Parameters and Details",
    "Current Balance": "Current Balance",
    "Tariff (₴/m²)": "Tariff (₴/m²)",
    "Expected Collection": "Expected Collection",
    "Update": "Update",
    "Debtors (Top 10)": "Debtors (Top 10)",
    "Expenses: Breakdown": "Expenses: Breakdown",
    "Apartment": "Apartment",
    "Owner": "Owner",
    "Debt": "Debt",
    "Group": "Group",
    "Amount": "Amount",
    "Total": "Total",
    "Other": "Other",
    "Type": "Type",
    "Purpose": "Purpose",
    "Dashboard error": "Dashboard error",
    "Inflows": "Inflows",
    "Expenses": "Expenses",
    "Balance": "Balance",
    "Details": "Details",
    "Parameters": "Parameters"
}

# In index.html, we don't need window.t() since lang.js walkTextNodes handles it automatically.
# But for app.js, we have dynamic innerHTML strings that need translation.

for word in replacements.keys():
    # Replace in innerHTML template literals >word< -> >${window.t('word')}<
    content = content.replace(f">{word}<", f">${{window.t('{word}')}}<")
    # Replace literal strings 'word' -> window.t('word')
    content = content.replace(f"'{word}'", f"window.t('{word}')")
    # Replace single quotes inside backticks e.g. `<p>word</p>`
    content = content.replace(f">{word} ", f">${{window.t('{word}')}} ")

with open('frontend/app.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("Applied window.t to app.js")
