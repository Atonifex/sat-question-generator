import os
import argparse
from dotenv import load_dotenv
from src.generator import QuestionGenerator
from src.reviser import QuestionReviser
from src.output_to_json import output_to_json
from src.config import DEFAULT_NUM_QUESTIONS, OUTPUT_DIR, VALID_SKILLS, VALID_DIFFICULTIES
from datetime import datetime
from pathlib import Path
import csv
from question_topics import literatureTopics, historyTopics, socialScienceTopics, hardScienceTopics, businessTechnologyTopics, philosophyPoliticalTopics, artMusicFilmSportsTopics, famousBiographies, modernTopicsAndFun


def main():
    # Load environment variables
    load_dotenv()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file_path = Path(OUTPUT_DIR) / f"questions_{timestamp}.csv"
    columns = ["timestamp", "raw_json", "skill", "difficulty", "question", "choices", "answer", "explanation",
            "Initial Feedback", "P2-Revised JSON", "Revised Question", "Revised Choices", "Revised Answer", "Revised Explanation",
            "Low Level Student Simulation", "High Level Student Simulation", "Question Rating", "Explanation Rating", "Constructive Feedback", "Final JSON SAT Question"]

    with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
       writer = csv.DictWriter(f, fieldnames=columns)
       writer.writeheader()
    
    # Initialize generator
    generator = QuestionGenerator(csv_file_path)
    #QuestionReviser writes the question, feedback, and revised question to same csv
    reviser = QuestionReviser(csv_file_path)

    topics = [literatureTopics, historyTopics, socialScienceTopics, hardScienceTopics, businessTechnologyTopics, philosophyPoliticalTopics, artMusicFilmSportsTopics, famousBiographies, modernTopicsAndFun]
    topicChoice = 0 # Used to change topics (literature, history, etc.)
    topicIndex = 0 #This is used to cycle through topics once topicIndex 0 has been done for all. Increments each time, so the real start is 0

    #Later on when doing the big loop, it could go:
    for skill in VALID_SKILLS:
         for difficulty in VALID_DIFFICULTIES:
            for q in range(DEFAULT_NUM_QUESTIONS):
                try:
                    if topicChoice % len(topics) == 0:
                        topicChoice = 0
                        topicIndex += 1
                    print(f"Generating {difficulty} {skill} question on topic {topicChoice[topicIndex]}")
                    questions = generator.generate_batch(skill, difficulty, 1, topics[topicChoice][topicIndex])  # Pass the current topic
                    
                    revised_questions = reviser.revise_batch(questions)

                    output_to_json(revised_questions)

                    print(f"FINISHED generating and revising {len(revised_questions)} questions for {difficulty} {skill}")
                    topicChoice += 1
                except Exception as e:
                    print(f"Error during generation or revision of {difficulty} {skill}: {e}")
                    topicChoice += 1
                #pretty sure saving to CSV is handled internally in the generate_batch & revise_questions functions

if __name__ == "__main__":
    main()





    """ Parse command-line arguments
    parser = argparse.ArgumentParser(description="Generate SAT questions.")
    parser.add_argument("--skill", type=str, required=True, help="Skill to generate questions for")
    parser.add_argument("--difficulty", type=str, required=True, choices=["Easy", "Medium", "Hard"], help="Difficulty level")
    parser.add_argument("--num_questions", type=int, default=5, help="Number of questions to generate")
    args = parser.parse_args()
    """