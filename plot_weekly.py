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
            
            # Calculate week number
            year_week = date.strftime('%Y-W%U')  # %U for week number starting from Sunday
            
            processed_data.append({
                'date': date,
                'author': author,
                'comment_lines': comment_lines,
                'comment_lines_density': comment_density,
                'total_changed_files_comments': total_changed_comments,
                'year_week': year_week
            })
        except Exception as e:
            logging.error(f"Error processing entry: {e}")
            
    return pd.DataFrame(processed_data)

def calculate_weekly_averages(df, metric):
    """Calculate weekly averages for the specified metric."""
    weekly_avg = df.groupby('year_week')[metric].mean().reset_index()
    return weekly_avg

def calculate_weekly_averages_by_author(df, metric):
    """Calculate weekly averages per author for the specified metric."""
    weekly_author_avg = df.groupby(['year_week', 'author'])[metric].mean().reset_index()
    return weekly_author_avg

def plot_weekly_averages(weekly_avg, metric, output_dir='plot'):
    """Create plot for weekly averages of the specified metric."""
    os.makedirs(output_dir, exist_ok=True)
    
    plt.figure(figsize=(15, 6))  # Made wider to accommodate more data points
    plt.plot(weekly_avg['year_week'], weekly_avg[metric], marker='o', markersize=3)
    plt.title(f'Average Weekly {metric.replace("_", " ").title()}')
    plt.xticks(rotation=90)
    
    # Only show every nth tick to prevent overcrowding
    n = max(1, len(weekly_avg) // 20)  # Show about 20 ticks
    plt.gca().xaxis.set_major_locator(plt.IndexLocator(base=n, offset=0))
    
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f'weekly_{metric.replace(" ", "_")}.png'), dpi=300)
    plt.close()

def plot_author_weekly_averages(df, output_dir='plot'):
    """Create plots for weekly averages by author for each metric."""
    os.makedirs(output_dir, exist_ok=True)
    
    metrics = ['comment_lines', 'comment_lines_density', 'total_changed_files_comments']
    
    for metric in metrics:
        author_dir = os.path.join(output_dir, metric.replace(" ", "_"))
        os.makedirs(author_dir, exist_ok=True)
        
        weekly_author_avg = calculate_weekly_averages_by_author(df, metric)
        
        for author in weekly_author_avg['author'].unique():
            author_data = weekly_author_avg[weekly_author_avg['author'] == author]
            
            plt.figure(figsize=(15, 6))  # Made wider to accommodate more data points
            plt.plot(author_data['year_week'], author_data[metric], marker='o', markersize=3)
            plt.title(f'Average Weekly {metric.replace("_", " ").title()} for {author}')
            plt.xticks(rotation=90)
            
            # Only show every nth tick to prevent overcrowding
            n = max(1, len(author_data) // 20)  # Show about 20 ticks
            plt.gca().xaxis.set_major_locator(plt.IndexLocator(base=n, offset=0))
            
            plt.grid(True)
            plt.tight_layout()
            plt.savefig(os.path.join(author_dir, f'{author.replace(" ", "_")}_weekly_{metric.replace(" ", "_")}.png'), dpi=300)
            plt.close()

def main():
    # Load and process data
    logging.info("Loading JSON files...")
    data = load_json_files()
    
    logging.info("Processing data into DataFrame...")
    df = process_data_to_dataframe(data)
    
    # Sort DataFrame by date to ensure chronological order
    df = df.sort_values('date')
    
    # Calculate and plot weekly averages
    logging.info("Calculating and plotting weekly averages...")
    for metric in ['comment_lines', 'comment_lines_density', 'total_changed_files_comments']:
        weekly_avg = calculate_weekly_averages(df, metric)
        plot_weekly_averages(weekly_avg, metric)
    
    logging.info("Calculating and plotting author weekly averages...")
    plot_author_weekly_averages(df)
    
    logging.info("Analysis complete!")

if __name__ == "__main__":
    main()