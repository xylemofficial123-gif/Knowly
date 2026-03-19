import sys
import os
import logging

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.drive_ingestion import _get_drive_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_id_metadata(target_id):
    service = _get_drive_service()
    
    try:
        logger.info(f"Checking metadata for ID: {target_id}")
        f = service.files().get(
            fileId=target_id,
            fields="id, name, mimeType, trashed, parents"
        ).execute()
        
        print("\nMetadata found:")
        print(f"  Name: {f.get('name')}")
        print(f"  Type: {f.get('mimeType')}")
        print(f"  Trashed: {f.get('trashed')}")
        print(f"  Parents: {f.get('parents')}")
        
    except Exception as e:
        print(f"\nFailed to get metadata: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/check_drive_id.py <id>")
        sys.exit(1)
    
    check_id_metadata(sys.argv[1])
