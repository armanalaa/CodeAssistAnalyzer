import json
import os
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict
import logging


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_json_files(json_dir='json'):
    """Load all JSON files from the specified directory into a list."""
    data = []
    for filename in os.listdir(json_dir):
        if filename.endswith('.json'):
            try:
                with open(os.path.join(json_dir, filename), 'r') as f:
                    json_data = json.load(f)
                    data.append(json_data)
            except Exception as e:
                logging.error(f"Error loading {filename}: {e}")
    return data

def process_data_to_dataframe(data):
    """Convert JSON data to a pandas DataFrame with processed dates."""
    processed_data = []

    for entry in data:
        try:
            # Extract basic information
            date = pd.to_datetime(entry['date'])
            author = entry['author']

            # Extract metrics
            metrics = entry['overall_comment_metrics']
            comment_lines = int(metrics.get('comment_lines', 0))
            comment_density = float(metrics.get('comment_lines_density', 0))
            total_changed_comments = entry.get('total_changed_files_comments', 0)

            # Append processed information to the list
            processed_data.append({
                'date': date,
                'author': author,
                'comment_lines': comment_lines,
                'comment_lines_density': comment_density,
                'total_changed_files_comments': total_changed_comments,
                'year_month': date.strftime('%Y-%m')
            })
        except Exception as e:
            logging.error(f"Error processing entry: {e}")

    # Convert the list of dictionaries to a pandas DataFrame
    df = pd.DataFrame(processed_data)

    # Log the DataFrame creation step
    if 'year_month' not in df.columns:
        logging.error("'year_month' column is missing after processing. Please check the data.")
    else:
        logging.info("'year_month' column successfully added to DataFrame.")

    return df
    
def calculate_quarterly_averages(df, metric):
    """Calculate quarterly averages for the specified metric."""
    if 'year_month' not in df.columns:
        logging.error("'year_month' column not found in DataFrame.")
        return pd.DataFrame()  # Return empty DataFrame to avoid crashing

    try:
        # Make a copy of the DataFrame to prevent modifying the original DataFrame
        df_copy = df.copy()

        # Convert year_month to datetime and set as index
        df_copy['year_month'] = pd.to_datetime(df_copy['year_month'], format='%Y-%m')
        df_copy.set_index('year_month', inplace=True)

        # Resample quarterly and calculate mean for each quarter
        # 'E-DEC' means end of the year in December, which indicates that each year is broken into quarters ending in March, June, September, and December.
        quarterly_avg = df_copy.resample('QE-DEC')[metric].mean().reset_index()
        return quarterly_avg  # Ensure that a DataFrame is returned here.
    except KeyError as e:
        logging.error(f"KeyError while calculating quarterly averages: {e}")
    except Exception as e:
        logging.error(f"Unexpected error while calculating quarterly averages: {e}")

    return pd.DataFrame()  # Return empty DataFrame if any exception occurs

def plot_quarterly_averages(quarterly_avg, metric, output_dir='plot'):
    """Create plot for quarterly averages of the specified metric."""
    if quarterly_avg is None or quarterly_avg.empty:
        logging.warning(f"Quarterly averages DataFrame for {metric} is empty or None. Skipping plot.")
        return

    os.makedirs(output_dir, exist_ok=True)
    
    plt.figure(figsize=(12, 6))
    plt.plot(quarterly_avg['year_month'], quarterly_avg[metric], marker='o')
    plt.title(f'Average Quarterly {metric.capitalize()}')
    plt.xticks(rotation=90)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f'quarterly_{metric.replace(" ", "_")}.png'))
    plt.close()

def main():
    logging.info("Loading JSON files...")
    data = load_json_files()
    
    logging.info("Processing data into DataFrame...")
    df = process_data_to_dataframe(data)

    # Add a check here to ensure the DataFrame is not empty
    if df.empty:
        logging.error("Processed DataFrame is empty. Exiting script.")
        return
    
    # Calculate and plot quarterly averages
    logging.info("Calculating and plotting quarterly averages...")
    for metric in ['comment_lines', 'comment_lines_density', 'total_changed_files_comments']:
        quarterly_avg = calculate_quarterly_averages(df, metric)
        plot_quarterly_averages(quarterly_avg, metric)
    
    logging.info("Analysis complete!")

if __name__ == "__main__":
    main()