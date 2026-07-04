import random
import csv

with open('workspace/dirty_data.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['id', 'age', 'income', 'churn'])
    for i in range(1, 101):
        age = random.choice([random.randint(18, 65), ''])
        income = random.choice([random.randint(20000, 100000), ''])
        churn = random.choice([0, 1, ''])
        writer.writerow([i, age, income, churn])

with open('workspace/model_docs.md', 'w', encoding='utf-8') as f:
    f.write("# Churn Model Documentation\n\nThis model predicts user churn based on age and income.\nTarget variable is `churn`. Note that `dirty_data.csv` contains missing values which must be handled before training.\n")
