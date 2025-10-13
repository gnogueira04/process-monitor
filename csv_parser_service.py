import csv
import json
import sys
import time
from datetime import datetime
import argparse
import itertools
import os

def tail_csv_and_convert(input_file, output_file, interval=5):
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

    print(f"Starting to monitor '{input_file}' for new lines...")
    print(f"New entries will be appended to '{output_file}'.")
    
    processed_line_count = 0

    try:
        while True:
            try:
                with open(input_file, mode='r', encoding='utf-8', newline='') as infile:
                    reader = csv.DictReader(infile)
                    
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
                                    print(f"Warning: Could not parse timestamp '{row.get('timestamp')}'. Skipping row. Error: {e}")
                                    continue
                            else:
                                print("Warning: 'timestamp' column not found. Skipping row.")
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
                        print(f"Processed {new_lines_found} new line(s). Total processed: {processed_line_count}")
                    else:
                        print("No new lines detected. Waiting...")

            except FileNotFoundError:
                print(f"Warning: Input file not found at '{input_file}'. Will retry in {interval} seconds.")
            except Exception as e:
                print(f"An error occurred: {e}. Will retry in {interval} seconds.")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Continuously monitors a CSV file for new lines and converts them to a JSONL file for Loki.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("input_csv", help="The path to the source CSV file to monitor.")
    parser.add_argument("output_jsonl", help="The path to the destination JSONL file to be appended.")
    parser.add_argument("--interval", type=int, default=5, help="The interval in seconds to check for new lines (default: 5).")

    args = parser.parse_args()
    
    tail_csv_and_convert(args.input_csv, args.output_jsonl, args.interval)

