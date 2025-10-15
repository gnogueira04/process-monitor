import csv
import json
import time
from datetime import datetime
import argparse
import itertools
import logging
from logging.handlers import TimedRotatingFileHandler
import sys

def setup_logging(log_file):
    """
    Sets up a logger that rotates its log file daily at midnight.
    Old log files are kept for 7 days.
    """
    # Get the logger instance
    logger = logging.getLogger("CSVConverterLogger")
    logger.setLevel(logging.INFO)  # Set the minimum level of messages to log

    # Prevent the log messages from being duplicated in the console
    logger.propagate = False

    # Create a handler for rotating log files.
    # 'midnight' specifies the rotation time.
    # interval=1 means rotate every day.
    # backupCount=7 means keep the last 7 log files.
    handler = TimedRotatingFileHandler(
        log_file, 
        when='midnight', 
        interval=1, 
        backupCount=7
    )
    
    # Define the format for the log messages
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)

    # Add the handler to the logger if it doesn't have one already
    if not logger.handlers:
        logger.addHandler(handler)
        # Also add a handler to print logs to the console for real-time feedback
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

def tail_csv_and_convert(input_file, output_file, logger, interval=5):
    """
    Continuously monitors a CSV file for new lines, processes them, 
    and appends them to a JSON Lines file.
    """

    numeric_fields = [
        'fps', 'win_packets', 'win_lost', 'win_late', 'win_dup', 'win_loss_pct',
        'acc_packets', 'acc_lost', 'acc_loss_pct', 'avg_jitter_ms', 'bitrate_kbps',
        'rtp_in', 'rtp_gaps', 'rtp_ooo', 'buf_corrupted', 'buf_discont',
        'buf_gapflag', 'gap_events', 'qos_dropped', 'late_avg_ms', 'late_max_ms'
    ]

    logger.info(f"Starting to monitor '{input_file}' for new lines...")
    logger.info(f"New entries will be appended to '{output_file}'.")
    logger.info(f"Log messages will be written to the configured log file.")
    
    processed_line_count = 0

    try:
        while True:
            try:
                with open(input_file, mode='r', encoding='utf-8', newline='') as infile:
                    reader = csv.DictReader(infile)
                    
                    # Skip lines that have already been processed
                    new_rows = itertools.islice(reader, processed_line_count, None)
                    
                    new_lines_found = 0
                    
                    with open(output_file, mode='a', encoding='utf-8') as outfile:
                        for row in new_rows:
                            processed_row = {}
                            original_ts_obj = None

                            if 'timestamp' in row:
                                try:
                                    original_ts_obj = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                                except (ValueError, TypeError) as e:
                                    logger.warning(f"Could not parse timestamp '{row.get('timestamp')}'. Skipping row. Error: {e}")
                                    continue
                            else:
                                logger.warning("'timestamp' column not found. Skipping row.")
                                continue

                            for key, value in row.items():
                                if key in numeric_fields:
                                    try:
                                        processed_row[key] = float(value)
                                    except (ValueError, TypeError):
                                        processed_row[key] = None
                                elif key == 'timestamp':
                                    processed_row[key] = original_ts_obj.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                                else:
                                    processed_row[key] = value
                            
                            outfile.write(json.dumps(processed_row) + '\n')
                            new_lines_found += 1
                    
                    if new_lines_found > 0:
                        processed_line_count += new_lines_found
                        logger.info(f"Processed {new_lines_found} new line(s). Total processed: {processed_line_count}")
                    else:
                        logger.info("No new lines detected. Waiting...")

            except FileNotFoundError:
                logger.warning(f"Input file not found at '{input_file}'. Will retry in {interval} seconds.")
            except Exception as e:
                # exc_info=True will log the full traceback for debugging
                logger.error(f"An unhandled error occurred. Will retry in {interval} seconds.", exc_info=True)

            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Continuously monitors a CSV file for new lines and converts them to a JSONL file for Loki.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("input_csv", help="The path to the source CSV file to monitor.")
    parser.add_argument("output_jsonl", help="The path to the destination JSONL file to be appended.")
    parser.add_argument("--interval", type=int, default=5, help="The interval in seconds to check for new lines (default: 5).")
    parser.add_argument("--log-file", default="logs/csv_converter.log", help="Path to the log file (default: csv_converter.log).")


    args = parser.parse_args()
    
    # Set up logging before starting the main process
    logger = setup_logging(args.log_file)
    
    try:
        tail_csv_and_convert(args.input_csv, args.output_jsonl, logger, args.interval)
    except Exception as e:
        logger.critical("A critical error occurred in the main execution block.", exc_info=True)
        sys.exit(1)
