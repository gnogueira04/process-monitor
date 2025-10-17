import csv
import json
import time
from datetime import datetime, timedelta, timezone
import argparse
import itertools
import logging
from logging.handlers import TimedRotatingFileHandler
import sys
import os

def setup_logging(log_file):
    """
    Sets up a logger that rotates its log file daily at midnight.
    Old log files are kept for 7 days.
    """
    logger = logging.getLogger("CSVConverterLogger")
    logger.setLevel(logging.INFO)  

    logger.propagate = False

    # 'midnight' specifies the rotation time.
    # interval=1 means rotate every day.
    # backupCount=7 means keep the last 7 log files.
    handler = TimedRotatingFileHandler(
        log_file, 
        when='midnight', 
        interval=1, 
        backupCount=7
    )
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(handler)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

def prune_file(file_path, retention_days, file_type, logger):
    """
    Rewrites a CSV or JSONL file, keeping only records within the retention period.
    Returns the number of lines kept, or None on failure.
    """
    logger.info(f"Pruning '{file_path}' to keep the last {retention_days} days of data...")
    
    if not os.path.exists(file_path):
        logger.warning(f"File '{file_path}' not found. Skipping pruning.")
        return None

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
    temp_file_path = file_path + ".tmp"
    
    initial_line_count = 0
    kept_line_count = 0

    try:
        with open(file_path, 'r', encoding='utf-8', newline='') as infile, \
             open(temp_file_path, 'w', encoding='utf-8', newline='') as outfile:
            
            if file_type == 'csv':
                reader = csv.DictReader(infile)
                if not reader.fieldnames:
                    logger.warning(f"CSV file '{file_path}' is empty or has no header. Pruning skipped.")
                    os.remove(temp_file_path)
                    return 0
                
                writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
                writer.writeheader()
                
                for row in reader:
                    initial_line_count += 1
                    timestamp_str = row.get('timestamp')

                    if timestamp_str == 'timestamp':
                        logger.warning("Skipping a header-like row found in the CSV body during pruning.")
                        continue

                    if not timestamp_str:
                        logger.warning(f"Row lacks 'timestamp', keeping it. Row: {row}")
                        writer.writerow(row)
                        kept_line_count += 1
                        continue
                    
                    try:
                        ts_obj = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        if ts_obj.tzinfo is None:
                            ts_obj = ts_obj.replace(tzinfo=timezone.utc)
                        
                        if ts_obj >= cutoff_date:
                            writer.writerow(row)
                            kept_line_count += 1
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse timestamp '{timestamp_str}', keeping row. Row: {row}")
                        writer.writerow(row)
                        kept_line_count += 1
                        
            elif file_type == 'jsonl':
                for line in infile:
                    initial_line_count += 1
                    try:
                        data = json.loads(line)
                        timestamp_str = data.get('timestamp')
                        if not timestamp_str:
                            logger.warning(f"Record lacks 'timestamp', keeping it. Record: {line.strip()}")
                            outfile.write(line)
                            kept_line_count += 1
                            continue
                        
                        ts_obj = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        if ts_obj.tzinfo is None:
                            ts_obj = ts_obj.replace(tzinfo=timezone.utc)

                        if ts_obj >= cutoff_date:
                            outfile.write(line)
                            kept_line_count += 1
                    except (json.JSONDecodeError, ValueError, TypeError):
                        logger.warning(f"Could not parse line, keeping it. Line: {line.strip()}")
                        outfile.write(line)
                        kept_line_count += 1
            else:
                logger.error(f"Unknown file type '{file_type}' for pruning.")
                return None

        os.replace(temp_file_path, file_path)
        removed_count = initial_line_count - kept_line_count
        logger.info(f"Pruning of '{file_path}' complete. Kept {kept_line_count} lines, removed {removed_count}.")
        
        return kept_line_count

    except Exception:
        logger.error(f"An error occurred during pruning of '{file_path}'. Operation aborted.", exc_info=True)
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        return None


def tail_csv_and_convert(input_file, output_file, logger, interval=5, retention_days=0):
    """
    Continuously monitors a CSV file for new lines, processes them, 
    and appends them to a JSON Lines file.
    Periodically prunes old records from both files if retention_days is set.
    """

    numeric_fields = [
        'fps', 'win_packets', 'win_lost', 'win_late', 'win_dup', 'win_loss_pct',
        'acc_packets', 'acc_lost', 'acc_loss_pct', 'avg_jitter_ms', 'bitrate_kbps',
        'rtp_in', 'rtp_gaps', 'rtp_ooo', 'buf_corrupted', 'buf_discont',
        'buf_gapflag', 'gap_events', 'qos_dropped', 'late_avg_ms', 'late_max_ms'
    ]

    last_cleanup_time = 0
    cleanup_interval_seconds = 6 * 60 * 60  

    logger.info(f"Starting to monitor '{input_file}' for new lines...")
    logger.info(f"New entries will be appended to '{output_file}'.")
    if retention_days > 0:
        logger.info(f"Data retention is enabled. Records older than {retention_days} days will be pruned.")
    
    processed_line_count = 0

    try:
        while True:
            if retention_days > 0 and time.time() - last_cleanup_time > cleanup_interval_seconds:
                prune_file(output_file, retention_days, 'jsonl', logger)

                new_csv_line_count = prune_file(input_file, retention_days, 'csv', logger)

                if new_csv_line_count is not None:
                    logger.info(f"Resetting processed line count to {new_csv_line_count} after CSV pruning.")
                    processed_line_count = new_csv_line_count
                
                last_cleanup_time = time.time()
            try:
                new_rows_in_memory = []
                try:
                    with open(input_file, mode='r', encoding='utf-8', newline='') as infile:
                        reader = csv.DictReader(infile)
                        new_rows_iterator = itertools.islice(reader, processed_line_count, None)
                        new_rows_in_memory = list(new_rows_iterator)
                except FileNotFoundError:
                    logger.warning(f"Input file not found at '{input_file}'. Will retry in {interval} seconds.")
                    time.sleep(interval)
                    continue 
                
                if new_rows_in_memory:
                    new_lines_found = 0
                    with open(output_file, mode='a', encoding='utf-8') as outfile:
                        for row in new_rows_in_memory: 
                            processed_row = {}
                            original_ts_obj = None

                            if 'timestamp' in row and row['timestamp']:
                                try:
                                    original_ts_obj = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                                    if original_ts_obj.tzinfo is None:
                                        original_ts_obj = original_ts_obj.replace(tzinfo=timezone.utc)
                                except (ValueError, TypeError) as e:
                                    logger.warning(f"Could not parse timestamp '{row.get('timestamp')}'. Skipping row. Error: {e}")
                                    continue
                            else:
                                logger.warning("'timestamp' column not found or empty. Skipping row.")
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
            except Exception as e:
                logger.error(f"An unhandled error occurred in the main processing loop.", exc_info=True)

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
    parser.add_argument(
        "--retention-days", 
        type=int, 
        default=7, 
        help="The number of days of data to keep. Deletes records older than this period. Set to 0 to disable (default: 0)."
    )

    args = parser.parse_args()
    
    logger = setup_logging(args.log_file)
    
    try:
        tail_csv_and_convert(args.input_csv, args.output_jsonl, logger, args.interval, args.retention_days)
    except Exception as e:
        logger.critical("A critical error occurred in the main execution block.", exc_info=True)
        sys.exit(1)

