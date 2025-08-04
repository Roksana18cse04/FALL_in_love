import pandas as pd
import os


from app.config import POLICY_CSV, CATEGORY_CSV 

def update_policy_view(policy_id, policy_name, category):
    # ========== POLICY LEVEL ==========
    if os.path.exists(POLICY_CSV):
        df_policy = pd.read_csv(POLICY_CSV)
    else:
        df_policy = pd.DataFrame(columns=["policy_id", "policy_name", "category", "view_count"])

    match = df_policy[df_policy['policy_id'] == policy_id]

    if not match.empty:
        df_policy.loc[df_policy['policy_id'] == policy_id, 'view_count'] += 1
    else:
        new_row = {
            "policy_id": policy_id,
            "policy_name": policy_name,
            "category": category,
            "view_count": 1
        }
        df_policy = pd.concat([df_policy, pd.DataFrame([new_row])], ignore_index=True)

    df_policy.to_csv(POLICY_CSV, index=False)

    # ========== CATEGORY LEVEL ==========
    if os.path.exists(CATEGORY_CSV):
        df_cat = pd.read_csv(CATEGORY_CSV)
    else:
        df_cat = pd.DataFrame(columns=["category", "view_count"])

    cat_match = df_cat[df_cat['category'] == category]

    if not cat_match.empty:
        df_cat.loc[df_cat['category'] == category, 'view_count'] += 1
    else:
        new_cat_row = {
            "category": category,
            "view_count": 1
        }
        df_cat = pd.concat([df_cat, pd.DataFrame([new_cat_row])], ignore_index=True)

    df_cat.to_csv(CATEGORY_CSV, index=False)

    print(f" View count updated for: {policy_name} | 📊 Category: {category}")


# === Example Usage ===
update_policy_view("P001", "Leave Policy", "HR")
update_policy_view("P002", "Medical Reimbursement", "Healthcare")
update_policy_view("P001", "Leave Policy", "HR")
update_policy_view("P003", "Work From Home Policy", "HR")
update_policy_view("P003", "Work From Home Policy", "HR")
update_policy_view("P002", "Medical Reimbursement", "Healthcare")
update_policy_view("P002", "Medical Reimbursement", "Healthcare")
update_policy_view("P002", "Medical Reimbursement", "Healthcare")
update_policy_view("P004", "Data Privacy Policy", "IT")
update_policy_view("P005", "Code of Conduct", "General")

