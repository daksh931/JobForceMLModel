import os
from flask import Flask, request, jsonify
from pymongo import MongoClient, errors
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

# Load MongoDB URI from environment variables
mongo_uri = os.getenv("MONGO_URI")

# MongoDB connection setup
def connect_to_mongo():
    try:
        # Attempt to establish a connection to MongoDB
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)  # Timeout after 5 seconds
        # Test the connection
        client.admin.command('ping')  # A simple command to check if MongoDB is reachable
        print("Connected to MongoDB successfully")
        return client
    except errors.ServerSelectionTimeoutError as err:
        # If connection fails
        print("Failed to connect to MongoDB:", err)
        return None

# Connect to MongoDB
client = connect_to_mongo()
if client:
    db = client["test"]  # Replace with your actual database name
    jobs_collection = db["jobs"]
    users_collection = db["users"]
else:
    # Graceful exit if unable to connect
    print("Exiting application due to MongoDB connection failure.")
    exit(1)

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

@app.route('/')
def hello():
    return {"Hello":"api deployed successfully"}

@app.route('/match-jobs', methods=['POST'])
def match_jobs():
    """Matches jobs for a given user ID."""
    data = request.json
    user_id = data.get('userId')

    # Ensure userId is provided in the request
    if not user_id:
        return jsonify({'error': 'User ID is required'}), 400

    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Get resume text from S3 URL
    resume_url = user.get('resumeUrl')
    if not resume_url:
        return jsonify({'error': 'User resume URL is missing'}), 400

    resume_text = extract_text_from_pdf(resume_url)

    if not resume_text:
        return jsonify({'error': 'Failed to extract text from resume'}), 400

    # Extract skills from resume
    user_skills = extract_skills_from_resume(resume_text)

    # Fetch available jobs from MongoDB
    job_descriptions = list(jobs_collection.find())
    if not job_descriptions:
        return jsonify({'error': 'No jobs available'}), 404

    # Match the user's skills with job descriptions
    recommended_jobs = matching(user_skills, job_descriptions)

    return jsonify({'recommended_jobs': recommended_jobs})

def extract_text_from_pdf(url):
    """Downloads a PDF from a URL and extracts text."""
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises HTTPError for bad responses
        if response.status_code == 200:
            pdf_file = BytesIO(response.content)
            text = ""
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
            return text.strip()
    except requests.exceptions.RequestException as err:
        print(f"Error fetching PDF: {err}")
    return ""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
