import subprocess  # Import subprocess module to run shell commands from Python
import json  # Import JSON module to handle JSON data
import base64  # Import base64 module for encoding and decoding strings
import requests  # Import requests module to make HTTP requests
from datetime import datetime  # Import datetime class for date and time operations
import logging  # Import logging module to enable logging functionality
import os  # Import os module for interacting with the operating system

# Set up logging configuration with INFO level and specify log message format
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define SonarQube token for authentication
SONARQUBE_TOKEN = 'squ_283ee66df42d4c8d217b4ff7bf5946acc877dacc'

# Define SonarQube host URL and project key for analysis
SONARQUBE_HOST = 'http://localhost:9000'
PROJECT_KEY = 'petastorm'

# Create an authentication token for SonarQube by encoding the SonarQube token in base64 format
auth_token = base64.b64encode(f'{SONARQUBE_TOKEN}:'.encode()).decode('utf-8')
# Set up the authorization header to be used in HTTP requests to SonarQube
headers = {'Authorization': f'Basic {auth_token}'}

# Create a directory named 'json' if it does not exist already
os.makedirs('json', exist_ok=True)

# Function to fetch comment-related metrics for the entire project from SonarQube
def get_comment_metrics():
    logging.info("Fetching comment-related metrics for the project...")  # Log the action
    # Define the API endpoint URL to fetch metrics from SonarQube
    url = f"{SONARQUBE_HOST}/api/measures/component"
    params = {
        'component': PROJECT_KEY,
        'metricKeys': 'comment_lines,comment_lines_density'
    }

    # Try making an HTTP GET request to SonarQube API to retrieve project metrics
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()  # Raise an exception if the HTTP request returned an error status
        project_data = response.json()  # Parse the response JSON data
        logging.debug(f"API response: {project_data}")  # Log the raw API response in debug mode

        # Check if metrics are available in the response and extract them
        if 'component' in project_data and 'measures' in project_data['component']:
            metrics = {measure['metric']: measure['value'] for measure in project_data['component']['measures']}
            logging.info(f"Comment metrics: {metrics}")  # Log the retrieved metrics
            return metrics  # Return the extracted metrics
        else:
            logging.warning("No comment data found for the project.")  # Log a warning if no data is found
            return {}  # Return an empty dictionary if no data is available
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to retrieve data: {e}")  # Log the error message
        return {}  # Return an empty dictionary if an error occurs

# Function to read commit hashes from a specified text file
def read_commit_hashes(filename='commit_hashes.txt'):
    logging.info(f"Reading commit hashes from {filename}...")  # Log the action
    try:
        with open(filename, 'r') as file:
            commit_hashes = [line.strip() for line in file.readlines()]  # Read and strip whitespace from each line
        logging.info(f"Found {len(commit_hashes)} commits.")  # Log the number of commits found
        return commit_hashes  # Return the list of commit hashes
    except FileNotFoundError:
        logging.error(f"The file {filename} was not found. Ensure the file exists and try again.")  # Log an error message
        return []  # Return an empty list if the file is not found

# Function to check if a given commit has already been analyzed
def is_commit_analyzed(commit_hash):
    json_filename = f'json/{commit_hash}.json'
    return os.path.exists(json_filename)

# Function to get details of a given commit using Git
def get_commit_details(commit_hash):
    logging.info(f"Getting details for commit: {commit_hash}")  # Log the action
    commit_info = subprocess.check_output(
        ['git', 'show', '-s', '--format=%H|%an|%ad', '--date=iso', commit_hash],
        encoding='utf-8'
    )
    commit_hash, author, commit_date = commit_info.strip().split('|')
    commit_time = datetime.strptime(commit_date, "%Y-%m-%d %H:%M:%S %z")
    logging.debug(f"Commit details - Hash: {commit_hash}, Author: {author}, Date: {commit_time}")  # Log the commit details
    return commit_hash, author, commit_time

# Function to run SonarQube scanner on the current codebase
def run_sonar_scanner():
    logging.info("Running SonarQube scanner...")  # Log the action
    result = subprocess.run(
        [r'C:\sonar-scanner-6.1.0.4477-windows-x64\bin\sonar-scanner.bat'], 
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    logging.info(f"SonarQube scanner stdout: {result.stdout}")
    logging.info(f"SonarQube scanner stderr: {result.stderr}")
    logging.info(f"SonarQube scanner finished with return code: {result.returncode}")  # Log the return code
    return result.returncode == 0  # Return True if the scanner completed successfully

# Function to analyze each commit from the list of commit hashes
def analyze_commits(commit_hashes):
    logging.info("Starting commit analysis...")  # Log the action

    for i, commit_hash in enumerate(commit_hashes):
        logging.info(f"--------------------------")  # Log a separator for readability
        logging.info(f"Processing commit {commit_hash} ({i+1}/{len(commit_hashes)})")  # Log the progress

        if is_commit_analyzed(commit_hash):
            logging.info(f"Commit {commit_hash} has already been analyzed. Skipping...")
            continue

        logging.info(f"Analyzing commit {commit_hash}...")  # Log the start of analysis

        subprocess.run(['git', 'checkout', commit_hash], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        commit_hash, author, commit_time = get_commit_details(commit_hash)

        if run_sonar_scanner():
            overall_comment_metrics = get_comment_metrics()

            commit_data = {
                'commit_hash': commit_hash,
                'author': author,
                'date': commit_time.isoformat(),
                'overall_comment_metrics': overall_comment_metrics
            }
            json_filename = f'json/{commit_hash}.json'
            with open(json_filename, 'w') as json_file:
                json.dump(commit_data, json_file, indent=2)
            logging.info(f"Commit {commit_hash} analysis saved to {json_filename}")  # Log successful save
        else:
            logging.error(f"SonarQube scan failed for commit {commit_hash}")  # Log scan failure

if __name__ == "__main__":
    commit_hashes = read_commit_hashes('commit_hashes.txt')
    analyze_commits(commit_hashes)
