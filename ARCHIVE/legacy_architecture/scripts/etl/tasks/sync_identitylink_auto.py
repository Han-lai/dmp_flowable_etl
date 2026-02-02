#!/usr/bin/env python3
"""
Auto sync ACT_HI_IDENTITYLINK_0108 batches
保守策略：每次 1 個批次，休息 1 分鐘 (因資料量大)
"""

import sys
import logging
import time
import subprocess
from datetime import datetime

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

import os

def get_remaining_batches():
    """取得剩餘待同步的批次數量"""
    try:
        script_path = os.path.join(os.path.dirname(__file__), 'sync_identitylink_batches.py')
        result = subprocess.run([
            sys.executable, script_path, '--dry-run'
        ], capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode != 0:
            logger.warning(f"dry-run execution warning, return code: {result.returncode}")
        
        # Parse batch count from output
        lines = result.stdout.split('\n')
        for line in lines:
            if 'Total:' in line and 'batches' in line:
                count_str = line.split('Total:')[1].split('batches')[0].strip()
                return int(count_str)
        return 0
    except Exception as e:
        logger.error(f"Failed to get remaining batches: {e}")
        return 0

def sync_batch_group(batch_size=1):
    """同步一組批次"""
    try:
        logger.info(f"Starting sync of {batch_size} batches...")
        
        script_path = os.path.join(os.path.dirname(__file__), 'sync_identitylink_batches.py')
        result = subprocess.run([
            sys.executable, script_path, '--limit', str(batch_size)
        ], check=True)
        
        logger.info(f"OK: {batch_size} batches synced successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"ERROR: Batch sync failed: {e}")
        return False
    except Exception as e:
        logger.error(f"ERROR: Execution error: {e}")
        return False

def main():
    """Main program - auto sync all batches"""
    logger.info("Starting auto sync of ACT_HI_IDENTITYLINK_0108 batches")
    logger.info("Strategy: 1 batch per round, 1 minute rest between rounds (Conservative Mode)")
    
    batch_size = 1
    rest_minutes = 1  # 每次休息 1 分鐘
    total_synced = 0
    round_count = 0
    
    while True:
        # Check remaining batches
        remaining = get_remaining_batches()
        
        if remaining == 0:
            logger.info("All batches synced successfully!")
            break
        
        round_count += 1
        logger.info(f"\n{'='*80}")
        logger.info(f"Round {round_count} - {remaining} batches remaining")
        logger.info(f"{'='*80}")
        
        # Execute sync
        if sync_batch_group(batch_size):
            total_synced += batch_size
            logger.info(f"OK: Round {round_count} complete, total synced: {total_synced} batches")
            
            # Check if more batches remain
            remaining_after = get_remaining_batches()
            if remaining_after == 0:
                logger.info("All batches synced successfully!")
                break
            
            # Rest
            logger.info(f"Resting {rest_minutes} minute(s)...")
            time.sleep(rest_minutes * 60)
            
        else:
            logger.error("ERROR: Sync failed, stopping auto sync")
            sys.exit(1)
    
    # Final summary
    logger.info(f"\n{'='*80}")
    logger.info(f"Auto sync complete summary:")
    logger.info(f"Total rounds: {round_count}")
    logger.info(f"Total batches synced: {total_synced}")
    logger.info(f"{'='*80}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nAuto sync interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"ERROR: Auto sync failed: {e}")
        sys.exit(1)
