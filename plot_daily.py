import json
import os
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG level for more detail
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_json_files(json_dir='json'):
    """Load all JSON files from the specified directory into a list."""
    data = []
    logging.debug(f"Looking for JSON files in directory: {json_dir}")
    logging.debug(f"Current working directory: {os.getcwd()}")
    
    try:
        files = os.listdir(json_dir)
        logging.debug(f"Files found in directory: {files}")
        
        for filename in files:
            if filename.endswith('.json'):
                file_path = os.path.join(json_dir, filename)
                logging.debug(f"Processing file: {file_path}")
                try:
                    with open(file_path, 'r') as f:
                        json_data = json.load(f)
                        data.append(json_data)
                except Exception as e:
                    logging.error(f"Error loading {filename}: {e}")
    except Exception as e:
        logging.error(f"Error accessing directory {json_dir}: {e}")
        
    logging.info(f"Successfully loaded {len(data)} JSON files")
    if data:
        logging.debug(f"Sample of first entry: {data[0]}")
    return data

def process_data_to_dataframe(data):
    """Convert JSON data to a pandas DataFrame with processed dates."""
    processed_data = []
    logging.info(f"Processing {len(data)} entries")
    
    for i, entry in enumerate(data):
        try:
            # Parse the date string to datetime and convert to UTC
            date = pd.to_datetime(entry['date']).tz_convert('UTC')
            author = entry['author']
            metrics = entry['overall_comment_metrics']
            comment_lines = int(metrics.get('comment_lines', 0))
            comment_density = float(metrics.get('comment_lines_density', 0))
            total_changed_comments = entry.get('total_changed_files_comments', 0)
            
            processed_data.append({
                'date': date,
                'author': author,
                'comment_lines': comment_lines,
                'comment_lines_density': comment_density,
                'total_changed_files_comments': total_changed_comments
            })
            
            if i % 100 == 0:  # Log progress every 100 entries
                logging.debug(f"Processed {i} entries")
                
        except Exception as e:
            logging.error(f"Error processing entry {i}: {str(e)}")
            logging.error(f"Problematic entry: {entry}")
            
    df = pd.DataFrame(processed_data)
    
    # Convert dates to UTC and remove timezone information
    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
    df = df.sort_values('date')
    
    logging.info(f"Created DataFrame with shape: {df.shape}")
    if not df.empty:
        logging.debug("DataFrame head:")
        logging.debug(df.head())
        logging.debug("\nDataFrame info:")
        logging.debug(df.info())
    
    return df

def plot_daily_averages(df, metric, output_dir='plot'):
    """Create plot for daily averages of the specified metric."""
    logging.info(f"Creating daily average plot for {metric}")
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        logging.debug(f"Created/verified output directory: {output_dir}")
        
        # Group by date and calculate mean
        daily_avg = df.groupby(df['date'].dt.date)[metric].mean().reset_index()
        daily_avg['date'] = pd.to_datetime(daily_avg['date'])
        
        logging.debug(f"Calculated {len(daily_avg)} daily averages")
        
        plt.figure(figsize=(15, 6))
        plt.plot(daily_avg['date'], daily_avg[metric], marker='.', markersize=2, linewidth=1)
        plt.title(f'Daily Average {metric.replace("_", " ").title()}')
        
        plt.gcf().autofmt_xdate()
        plt.grid(True, alpha=0.3)
        plt.margins(x=0.02)
        
        # Add trend line
        x = np.arange(len(daily_avg))
        z = np.polyfit(x, daily_avg[metric], 1)
        p = np.poly1d(z)
        plt.plot(daily_avg['date'], p(x), "r--", alpha=0.8, label='Trend')
        
        plt.legend()
        plt.tight_layout()
        
        output_file = os.path.join(output_dir, f'daily_{metric}.png')
        plt.savefig(output_file, dpi=300)
        plt.close()
        
        logging.info(f"Saved plot to: {output_file}")
        
    except Exception as e:
        logging.error(f"Error creating plot for {metric}: {str(e)}")
        raise

def plot_author_daily_averages(df, output_dir='plot'):
    """Create plots for daily averages by author for each metric."""
    logging.info("Creating author-specific daily average plots")
    
    metrics = ['comment_lines', 'comment_lines_density', 'total_changed_files_comments']
    
    for metric in metrics:
        logging.info(f"Processing metric: {metric}")
        author_dir = os.path.join(output_dir, metric)
        os.makedirs(author_dir, exist_ok=True)
        
        unique_authors = df['author'].unique()
        logging.debug(f"Found {len(unique_authors)} unique authors")
        
        for author in unique_authors:
            try:
                logging.debug(f"Processing author: {author}")
                author_df = df[df['author'] == author]
                
                if len(author_df) < 2:
                    logging.debug(f"Skipping {author} - insufficient data points")
                    continue
                
                daily_avg = author_df.groupby(author_df['date'].dt.date)[metric].mean().reset_index()
                daily_avg['date'] = pd.to_datetime(daily_avg['date'])
                
                if len(daily_avg) < 2:
                    logging.debug(f"Skipping {author} - insufficient daily averages")
                    continue
                
                plt.figure(figsize=(15, 6))
                plt.plot(daily_avg['date'], daily_avg[metric], marker='.', markersize=2, linewidth=1)
                plt.title(f'Daily Average {metric.replace("_", " ").title()} for {author}')
                
                plt.gcf().autofmt_xdate()
                plt.grid(True, alpha=0.3)
                plt.margins(x=0.02)
                
                x = np.arange(len(daily_avg))
                z = np.polyfit(x, daily_avg[metric], 1)
                p = np.poly1d(z)
                plt.plot(daily_avg['date'], p(x), "r--", alpha=0.8, label='Trend')
                
                plt.legend()
                plt.tight_layout()
                
                safe_author = author.replace(" ", "_").replace("/", "_").replace("\\", "_")
                output_file = os.path.join(author_dir, f'{safe_author}_{metric}.png')
                plt.savefig(output_file, dpi=300)
                plt.close()
                
                logging.info(f"Saved plot for {author} to: {output_file}")
                
            except Exception as e:
                logging.error(f"Error creating plot for author {author}: {str(e)}")

def main():
    logging.info("Starting analysis...")
    
    # Check current directory and json directory
    cwd = os.getcwd()
    json_dir = os.path.join(cwd, 'json')
    logging.info(f"Current working directory: {cwd}")
    logging.info(f"JSON directory: {json_dir}")
    
    if not os.path.exists(json_dir):
        logging.error(f"JSON directory not found: {json_dir}")
        return
    
    data = load_json_files()
    if not data:
        logging.error("No data loaded from JSON files!")
        return
    
    df = process_data_to_dataframe(data)
    if df.empty:
        logging.error("DataFrame is empty!")
        return
    
    try:
        # Calculate and plot daily averages
        logging.info("Creating daily average plots...")
        for metric in ['comment_lines', 'comment_lines_density', 'total_changed_files_comments']:
            plot_daily_averages(df, metric)
        
        logging.info("Creating author-specific plots...")
        plot_author_daily_averages(df)
        
        logging.info("Analysis complete!")
        
    except Exception as e:
        logging.error(f"Error during plotting: {str(e)}")

if __name__ == "__main__":
    main()