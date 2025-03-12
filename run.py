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
from src.question_topics import literatureTopics, historyTopics, socialScienceTopics, hardScienceTopics, businessTechnologyTopics, philosophyPoliticalTopics, artMusicFilmSportsTopics, famousBiographies, modernTopicsAndFun


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
    topicChoice = 0  # Index for which topic list to use
    topicIndex = 0   # Index within the chosen topic list

    for skill in VALID_SKILLS:
        for difficulty in VALID_DIFFICULTIES:
            for q in range(DEFAULT_NUM_QUESTIONS):
                try:
                    # Get the current topic
                    current_topic_list = topics[topicChoice]
                    current_topic = current_topic_list[topicIndex % len(current_topic_list)]
                    
                    print(f"Generating {difficulty} {skill} question on topic: {current_topic}")
                    questions = generator.generate_batch(skill, difficulty, 1, current_topic)
                    
                    revised_questions = reviser.revise_batch(questions)

                    #Saving to CSV is handled internally in the revise_questions function
                    output_to_json(revised_questions)
                    print(f"FINISHED generating and revising {len(revised_questions)} questions for {difficulty} {skill}")
                    
                    # Update topic indices
                    topicIndex += 1
                    if topicIndex >= len(current_topic_list):
                        topicIndex = 0
                        topicChoice = (topicChoice + 1) % len(topics)
                        
                except Exception as e:
                    print(f"Error during generation or revision of {difficulty} {skill} on topic: {current_topic}: {e}")
                    # Still update topic indices even on error
                    topicIndex += 1
                    if topicIndex >= len(topics[topicChoice]):
                        topicIndex = 0
                        topicChoice = (topicChoice + 1) % len(topics)

if __name__ == "__main__":
    main()





    """ Parse command-line arguments
    parser = argparse.ArgumentParser(description="Generate SAT questions.")
    parser.add_argument("--skill", type=str, required=True, help="Skill to generate questions for")
    parser.add_argument("--difficulty", type=str, required=True, choices=["Easy", "Medium", "Hard"], help="Difficulty level")
    parser.add_argument("--num_questions", type=int, default=5, help="Number of questions to generate")
    args = parser.parse_args()
    """