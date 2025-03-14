import os
import argparse
from dotenv import load_dotenv
from src.generator import QuestionGenerator
from src.reviser import QuestionReviser
from src.output_to_json import output_to_json
from src.config import DEFAULT_NUM_QUESTIONS, OUTPUT_DIR, VALID_SKILLS, VALID_DIFFICULTIES, MATH_SKILLS
from datetime import datetime
from pathlib import Path
import csv
from src.question_topics import (literatureTopics, historyTopics, socialScienceTopics, hardScienceTopics, 
    businessTechnologyTopics, philosophyPoliticalTopics, artMusicFilmSportsTopics, famousBiographies, 
    modernTopicsAndFun)
import random


def main():
    # Load environment variables
    load_dotenv()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file_path = Path(OUTPUT_DIR) / f"questions_{timestamp}.csv"
    columns = ["timestamp", "raw_json", "skill", "difficulty", "question", "choices", "answer", "explanation",
            "Initial Feedback", "P2-Revised JSON", "Revised Question", "Revised Choices", "Revised Answer", "Revised Explanation",
            "Low Level Student Simulation", "High Level Student Simulation", "Question Rating", "Explanation Rating", "Constructive Feedback", "Difficulty Rating", "Total Score", "Final JSON SAT Question"]

    with open(csv_file_path, 'w', newline='', encoding='utf-8') as f:
       writer = csv.DictWriter(f, fieldnames=columns)
       writer.writeheader()
    
    # Initialize generator
    generator = QuestionGenerator(csv_file_path)
    #QuestionReviser writes the question, feedback, and revised question to same csv
    reviser = QuestionReviser(csv_file_path)

    # Create a list of topic lists and their names
    topics = [literatureTopics, historyTopics, socialScienceTopics, hardScienceTopics, 
              businessTechnologyTopics, philosophyPoliticalTopics, artMusicFilmSportsTopics, 
              famousBiographies, modernTopicsAndFun]
    
    # Create a list of topic list names for display purposes
    topic_names = ["literatureTopics", "historyTopics", "socialScienceTopics", "hardScienceTopics", 
                  "businessTechnologyTopics", "philosophyPoliticalTopics", "artMusicFilmSportsTopics", 
                  "famousBiographies", "modernTopicsAndFun"]
    
    topicChoice = 1  # Index for which topic list to use 
    topicIndex = 21   # Index within the chosen topic list - went up to line 1375 in CONSOLIDATED "In Mary Shelley's \"Frankenstein,\" by 3:00 am on 3/12.

    for skill in VALID_SKILLS:
        for difficulty in VALID_DIFFICULTIES:
            for q in range(DEFAULT_NUM_QUESTIONS):
                try:
                    if skill not in MATH_SKILLS: #Generate topic for Reading or Writing question but not Math. Double check this works on 3/15, but I think it's conservative and safe.
                        # Get the current topic
                        current_topic_list = topics[topicChoice]
                        current_topic_list_name = topic_names[topicChoice] #3/12: Added this to display the topic list name in console
                        current_topic = current_topic_list[topicIndex % len(current_topic_list)]
                        print(f"Generating {difficulty} {skill} question on topic {topicIndex} of {len(current_topic_list)} in list {current_topic_list_name}: {current_topic}")

                    else: #math
                        print(f"Generating {difficulty} {skill} question")
                    
                    questions = generator.generate_batch(skill, difficulty, 1, current_topic)
                    
                    #Saving to CSV is handled internally in the revise_questions function
                    revised_questions = reviser.revise_batch(questions)

                    # Add topic information to each question in the batch
                    for question in revised_questions: #there should only be 1 question, but this unpacks it.
                        question["topic_list_name"] = current_topic_list_name
                        question["topic_index"] = topicIndex

                    # Saving to CSV is handled internally in the revise_questions function
                    output_to_json(revised_questions)
                    print(f"FINISHED generating and revising {len(revised_questions)} questions for {difficulty} {skill}")
                    
                    if skill not in MATH_SKILLS: #Only increment topicIndex when we've gone through all topic lists
                        topicChoice = (topicChoice + 1) % len(topics)
                        if topicChoice == 0:  # We've wrapped around to the first topic list
                            topicIndex += 1   # Move to next index within all topic lists

                except Exception as e:
                    print(f"Error during generation or revision of {difficulty} {skill} on topic: {current_topic}: {e}")
                    #No need to update topic indices on error because they don't end up getting saved.


if __name__ == "__main__":
    main()





    """ Parse command-line arguments
    parser = argparse.ArgumentParser(description="Generate SAT questions.")
    parser.add_argument("--skill", type=str, required=True, help="Skill to generate questions for")
    parser.add_argument("--difficulty", type=str, required=True, choices=["Easy", "Medium", "Hard"], help="Difficulty level")
    parser.add_argument("--num_questions", type=int, default=5, help="Number of questions to generate")
    args = parser.parse_args()
    """