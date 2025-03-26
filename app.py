import os
from flask import Flask, request, jsonify
from pymongo import MongoClient
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
from io import BytesIO
import requests
import pdfplumber
from bson import ObjectId

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Connecting to MongoDB
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["test"]  # Replace with your actual database name
jobs_collection = db["jobs"]
users_collection = db["users"]

# Load spaCy model for skill extraction
nlp = spacy.load("en_core_web_sm")

def extract_skills_from_resume(resume_text):
    """Extracts noun-based skills from resume text."""
    doc = nlp(resume_text)
    skills = [token.text.lower() for token in doc if token.pos_ == "NOUN"]
    return " ".join(skills)  # Return as a single string for vectorization

def matching(user_skills, job_descriptions):
    """Matches user skills against job descriptions using TF-IDF and cosine similarity."""
    vectorizer = TfidfVectorizer()

    job_texts = [extract_skills_from_resume(job['description']) for job in job_descriptions]
    texts = [user_skills] + job_texts  # User skills + all job descriptions

    tfidf_matrix = vectorizer.fit_transform(texts)  # Convert text to vectors

    # Compute cosine similarity between user and all jobs
    user_vector = tfidf_matrix[0]  # First entry is the user
    job_vectors = tfidf_matrix[1:]  # Rest are jobs

    similarity_scores = cosine_similarity(user_vector, job_vectors)[0]  # Get 1D array
    recommended_jobs = sorted(zip([str(job['_id']) for job in job_descriptions], 
                                  [job['title'] for job in job_descriptions], similarity_scores),
                              key=lambda x: x[1], reverse=True)
    formatted_jobs = [
    {"jobId": job_id, "title": title, "score": score}
    for job_id, title, score in recommended_jobs
]

    return formatted_jobs

@app.route('/match-jobs', methods=['POST'])
def match_jobs():
    """Matches jobs for a given user ID."""
    data = request.json
    user_id = data.get('userId')

    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Get resume text from S3 URL
    resume_url = user.get('resumeUrl')
    resume_text = extract_text_from_pdf(resume_url)

    if not resume_text:
        return jsonify({'error': 'Failed to extract text from resume'}), 400

    # Extract skills from resume
    user_skills = extract_skills_from_resume(resume_text)

    # Fetch available jobs from MongoDB
    job_descriptions = list(jobs_collection.find())
    # job_descriptions = job_descriptions[:5]
    # print(job_descriptions)
    # Match the user's skills with job descriptions
    recommended_jobs = matching(user_skills, job_descriptions)

    return jsonify({'recommended_jobs': recommended_jobs})

def extract_text_from_pdf(url):
    """Downloads a PDF from a URL and extracts text."""
    response = requests.get(url)
    if response.status_code == 200:
        pdf_file = BytesIO(response.content)
        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    return ""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)