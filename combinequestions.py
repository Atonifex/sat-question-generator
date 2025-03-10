import pandas as pd
import json

# Path to your Excel file
excel_path = r"C:\Users\iharj\Documents\ChatGPT_or_Coding\SAT-question-generation\final-questions-270.xlsx"

# Read the Excel file
df = pd.read_excel(excel_path, engine='openpyxl')

# Extract the first column
data_column = df.iloc[0:, 1]  # Access second column by indexquestions_list = []

questions_list = []

# Iterate over each row in the column
for row in data_column:
    if pd.isna(row):  # Skip empty rows
        continue
    
    # Split data based on commas
    split_data = row.split(',')
    
    # Parse the split data into a JSON structure
    question_data = {
        "skill": split_data[0].strip() if len(split_data) > 0 else "Skill not provided",
        "difficulty": split_data[1].strip() if len(split_data) > 1 else "Difficulty not provided",
        "question": split_data[2].strip() if len(split_data) > 2 else "Question not provided",
        "choices": [
            f"A) {split_data[3].strip()}" if len(split_data) > 3 else "A) ",
            f"B) {split_data[4].strip()}" if len(split_data) > 4 else "B) ",
            f"C) {split_data[5].strip()}" if len(split_data) > 5 else "C) ",
            f"D) {split_data[6].strip()}" if len(split_data) > 6 else "D) ",
        ],
        "answer": split_data[7].strip() if len(split_data) > 7 else "",
        "explanation": split_data[8].strip() if len(split_data) > 8 else "Explanation not provided",
    }
    questions_list.append(question_data)
    print(row)


# Path to save the JSON file
output_path = r"C:\Users\iharj\Documents\ChatGPT_or_Coding\SAT-question-generation\formatted-final-questions.json"

print(df.columns)
print(df.head())


# Save the JSON to a file
with open(output_path, "w", encoding="utf-8") as json_file:
    json.dump(questions_list, json_file, indent=4, ensure_ascii=False)

print(f"JSON saved to: {output_path}")
