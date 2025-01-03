import subprocess  # Import subprocess module to run shell commands from Python
import json  # Import JSON module to handle JSON data
import base64  # Import base64 module for encoding and decoding strings
import requests  # Import requests module to make HTTP requests
from datetime import datetime  # Import datetime class for date and time operations
import logging  # Import logging module to enable logging functionality
import os  # Import os module for interacting with the operating system
import matplotlib.pyplot as plt  # Import Matplotlib for plotting (currently not used in this script)
from collections import defaultdict  # Import defaultdict from collections to simplify dictionary usage

# Set up logging configuration with INFO level and specify log message format
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define SonarQube token for authentication
SONARQUBE_TOKEN = ''

# Define SonarQube host URL and project key for analysis
SONARQUBE_HOST = 'http://localhost:9000'
PROJECT_KEY = 'petastorm'

# Create an authentication token for SonarQube by encoding the SonarQube token in base64 format
auth_token = base64.b64encode(f'{SONARQUBE_TOKEN}:'.encode()).decode('utf-8')
# Set up the authorization header to be used in HTTP requests to SonarQube
headers = {'Authorization': f'Basic {auth_token}'}

# Create a directory named 'json' if it does not exist already
os.makedirs('json', exist_ok=True)
# Create a directory named 'plot' if it does not exist already
os.makedirs('plot', exist_ok=True)

# Function to fetch comment-related metrics for the entire project from SonarQube
def get_comment_metrics():
    logging.info("Fetching comment-related metrics for the project...")  # Log the action
    # Define the API endpoint URL to fetch metrics from SonarQube
    url = f"{SONARQUBE_HOST}/api/measures/component"
    # Set parameters to request only the metrics needed
    # comment_lines_density: The percentage of comment lines relative to the total number of lines (code + comments), indicating the extent of code documentation.
    
    
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
    # Handle exceptions related to the HTTP request
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to retrieve data: {e}")  # Log the error message
        return {}  # Return an empty dictionary if an error occurs

# Function to fetch comment metrics for an individual file from SonarQube
def get_file_comment_metrics(file_path):
    logging.info(f"Fetching comment metrics for file: {file_path}")  # Log the action for a specific file
    # Define the API endpoint URL to fetch file-level metrics from SonarQube
    url = f"{SONARQUBE_HOST}/api/measures/component"
    # Set parameters to request comment lines metric for the specific file
    params = {
        'component': f"{PROJECT_KEY}:{file_path}",
        'metricKeys': 'comment_lines'
    }

    # Try making an HTTP GET request to SonarQube API to retrieve file metrics
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()  # Raise an exception if the HTTP request returned an error status
        file_data = response.json()  # Parse the response JSON data

        # Check if metrics are available in the response and extract comment lines
        if 'component' in file_data and 'measures' in file_data['component']:
            comment_lines = next((int(measure['value']) for measure in file_data['component']['measures'] if measure['metric'] == 'comment_lines'), 0)
            logging.info(f"Comment lines for {file_path}: {comment_lines}")  # Log the number of comment lines
            return comment_lines  # Return the count of comment lines
        else:
            logging.warning(f"No comment data found for file: {file_path}")  # Log a warning if no data is found
            return 0  # Return 0 if no data is available
    # Handle exceptions related to the HTTP request
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to retrieve data for file {file_path}: {e}")  # Log the error message
        return 0  # Return 0 if an error occurs

# Function to read commit hashes from a specified text file
def read_commit_hashes(filename='commit_hashes.txt'):
    logging.info(f"Reading commit hashes from {filename}...")  # Log the action
    # Try reading the commit hashes from the specified file
    try:
        with open(filename, 'r') as file:
            commit_hashes = [line.strip() for line in file.readlines()]  # Read and strip whitespace from each line
        logging.info(f"Found {len(commit_hashes)} commits.")  # Log the number of commits found
        return commit_hashes  # Return the list of commit hashes
    # Handle the case where the file is not found
    except FileNotFoundError:
        logging.error(f"The file {filename} was not found. Ensure the file exists and try again.")  # Log an error message
        return []  # Return an empty list if the file is not found

# Function to check if a given commit has already been analyzed
def is_commit_analyzed(commit_hash):
    # Create the expected filename for the analyzed commit JSON
    json_filename = f'json/{commit_hash}.json'
    # Check if the JSON file already exists for this commit
    return os.path.exists(json_filename)

# Function to get details of a given commit using Git
def get_commit_details(commit_hash):
    logging.info(f"Getting details for commit: {commit_hash}")  # Log the action
    # Run a Git command to get commit hash, author, and date for the commit
    # -s: Show only commit info (like hash, author, date)
    # %H: The full commit hash.
    # %an: The author name.
    # %ad: The author date (formatted according to any date formatting options like --date=iso).

    commit_info = subprocess.check_output(
        ['git', 'show', '-s', '--format=%H|%an|%ad', '--date=iso', commit_hash],
        encoding='utf-8'
    )
    # Split the commit information string into its components
    commit_hash, author, commit_date = commit_info.strip().split('|')
    # Parse the commit date string into a datetime object
    commit_time = datetime.strptime(commit_date, "%Y-%m-%d %H:%M:%S %z")
    logging.debug(f"Commit details - Hash: {commit_hash}, Author: {author}, Date: {commit_time}")  # Log the commit details
    return commit_hash, author, commit_time  # Return the commit details

# Function to get the list of files changed in a given commit
def get_changed_files(commit_hash):
    logging.info(f"Getting changed files for commit: {commit_hash}")  # Log the action
    # Run a Git command to get a list of files changed in the specified commit
    # diff-tree: This Git command is used to compare a commit against its parent. It is most often used to inspect the differences in a commit—specifically, the tree structure of the files and folders.
    # --no-commit-id: This option tells Git not to display the commit ID when showing the output.
    # --name-only: This option instructs Git to only show the names of the files that were affected by the commit.
    # -r: When analyzing a commit, this ensures that all changes in the directory tree are displayed, including any files within subdirectories.
    
    changed_files = subprocess.check_output(
        ['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', commit_hash],
        encoding='utf-8'
    ).splitlines()
    logging.debug(f"Changed files: {changed_files}")  # Log the list of changed files
    return changed_files  # Return the list of changed files

# Function to run SonarQube scanner on the current codebase
def run_sonar_scanner():
    logging.info("Running SonarQube scanner...")  # Log the action
    # Run the SonarQube scanner command using subprocess
    # result = subprocess.run(
    #     [r'C:\sonar-scanner-6.1.0.4477-windows-x64\bin\sonar-scanner.bat'], 
    #     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    # )
    
        result = subprocess.run(
        [r''], 
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    
    # Log the scanner's standard output and error messages
    logging.info(f"SonarQube scanner stdout: {result.stdout}")
    logging.info(f"SonarQube scanner stderr: {result.stderr}")
    logging.info(f"SonarQube scanner finished with return code: {result.returncode}")  # Log the return code
    return result.returncode == 0  # Return True if the scanner completed successfully

# Function to analyze each commit from the list of commit hashes
def analyze_commits(commit_hashes):
    logging.info("Starting commit analysis...")  # Log the action

    # Loop over each commit in the list of commit hashes
    for i, commit_hash in enumerate(commit_hashes):
        logging.info(f"--------------------------")  # Log a separator for readability
        logging.info(f"Processing commit {commit_hash} ({i+1}/{len(commit_hashes)})")  # Log the progress

        # Skip the commit if it has already been analyzed
        if is_commit_analyzed(commit_hash):
            logging.info(f"Commit {commit_hash} has already been analyzed. Skipping...")  # Log skipping
            continue

        logging.info(f"Analyzing commit {commit_hash}...")  # Log the start of analysis

        # This is the Git command used to switch branches or move to a specific commit in the repository.
        # Checkout the specified commit in the Git repository
        # subprocess.run(): Runs a shell command from Python.
        # ['git', 'checkout', commit_hash]: Switches to the specified commit (commit_hash).
        # stdout=subprocess.PIPE: Captures command output (instead of printing it).
        # stderr=subprocess.PIPE: Captures error messages.
        # text=True: Ensures captured output is in string form, not bytes.
        
        subprocess.run(['git', 'checkout', commit_hash], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Get details of the commit
        commit_hash, author, commit_time = get_commit_details(commit_hash)

        # Get the list of files changed in the commit
        changed_files = get_changed_files(commit_hash)

        # Run SonarQube scanner to analyze the current state of the codebase
        if run_sonar_scanner():
            # Fetch overall comment metrics from SonarQube for the project
            overall_comment_metrics = get_comment_metrics()
            project_comments = int(overall_comment_metrics.get('comment_lines', 0))

            # Fetch comment metrics for each changed file in the commit
            changed_files_metrics = {}
            total_changed_files_comments = 0
            for file_path in changed_files:
                file_comments = get_file_comment_metrics(file_path)
                changed_files_metrics[file_path] = file_comments  # Store file-level comment metrics
                total_changed_files_comments += file_comments  # Increment total comment count

            # Create a dictionary to hold all commit data
            commit_data = {
                'commit_hash': commit_hash,
                'author': author,
                'date': commit_time.isoformat(),
                'overall_comment_metrics': overall_comment_metrics,
                'changed_files_metrics': changed_files_metrics,
                'total_changed_files_comments': total_changed_files_comments
            }
            # Define the filename for saving the commit analysis
            json_filename = f'json/{commit_hash}.json'
            # Save the commit analysis data to a JSON file
            with open(json_filename, 'w') as json_file:
                json.dump(commit_data, json_file, indent=2)
            logging.info(f"Commit {commit_hash} analysis saved to {json_filename}")  # Log successful save
        else:
            logging.error(f"SonarQube scan failed for commit {commit_hash}")  # Log scan failure

# Main entry point of the script
if __name__ == "__main__":
    # Read commit hashes from the specified file
    commit_hashes = read_commit_hashes('commit_hashes.txt')
    # Analyze all the commits read from the file
    analyze_commits(commit_hashes)
