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
            
    return pd.DataFrame(processed_data)

def calculate_monthly_averages(df, metric):
    """Calculate monthly averages for the specified metric."""
    monthly_avg = df.groupby('year_month')[metric].mean().reset_index()
    return monthly_avg

def calculate_monthly_averages_by_author(df, metric):
    """Calculate monthly averages per author for the specified metric."""
    monthly_author_avg = df.groupby(['year_month', 'author'])[metric].mean().reset_index()
    return monthly_author_avg

def plot_monthly_averages(monthly_avg, metric, output_dir='plot'):
    """Create plot for monthly averages of the specified metric."""
    os.makedirs(output_dir, exist_ok=True)
    
    plt.figure(figsize=(12, 6))
    plt.plot(monthly_avg['year_month'], monthly_avg[metric], marker='o')
    plt.title(f'Average Monthly {metric.capitalize()}')
    plt.xticks(rotation=90)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f'monthly_{metric.replace(" ", "_")}.png'))
    plt.close()

def plot_author_monthly_averages(df, output_dir='plot'):
    """Create plots for monthly averages by author for each metric."""
    os.makedirs(output_dir, exist_ok=True)
    
    for metric in ['comment_lines', 'comment_lines_density', 'total_changed_files_comments']:
        author_dir = os.path.join(output_dir, metric.replace(" ", "_"))
        os.makedirs(author_dir, exist_ok=True)
        
        monthly_author_avg = calculate_monthly_averages_by_author(df, metric)
        
        for author in monthly_author_avg['author'].unique():
            author_data = monthly_author_avg[monthly_author_avg['author'] == author]
            
            plt.figure(figsize=(12, 6))
            plt.plot(author_data['year_month'], author_data[metric], marker='o')
            plt.title(f'Average Monthly {metric.capitalize()} for {author}')
            plt.xticks(rotation=90)
            plt.grid(True)
            plt.tight_layout()
            plt.savefig(os.path.join(author_dir, f'{author.replace(" ", "_")}_monthly_{metric.replace(" ", "_")}.png'))
            plt.close()

def main():
    # Load and process data
    logging.info("Loading JSON files...")
    data = load_json_files()
    
    logging.info("Processing data into DataFrame...")
    df = process_data_to_dataframe(data)
    
    # Calculate and plot monthly averages
    logging.info("Calculating and plotting monthly averages...")
    for metric in ['comment_lines', 'comment_lines_density', 'total_changed_files_comments']:
        monthly_avg = calculate_monthly_averages(df, metric)
        plot_monthly_averages(monthly_avg, metric)
    
    logging.info("Calculating and plotting author monthly averages...")
    plot_author_monthly_averages(df)
    
    logging.info("Analysis complete!")

if __name__ == "__main__":
    main()