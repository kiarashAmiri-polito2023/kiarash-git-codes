import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
PROJECT_ROOT = r'D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1'

print('\n>>> BEGIN ROUND 10: VLA VISION DOMAIN & BEV AUDIT <<<')

sessions_dir = os.path.join(PROJECT_ROOT, 'sessions')

if os.path.exists(sessions_dir):
    total_images = 0
    total_videos = 0
    
    # Walk through all directories in sessions
    for root, dirs, files in os.walk(sessions_dir):
        images_in_dir = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        videos_in_dir = [f for f in files if f.lower().endswith(('.avi', '.mp4'))]
        
        if images_in_dir or videos_in_dir:
            folder_name = os.path.basename(root)
            print(f'\n[+] Directory: {folder_name}')
            if images_in_dir:
                print(f'  -> Found {len(images_in_dir)} BEV/Camera Image files (e.g., {images_in_dir[0]})')
                total_images += len(images_in_dir)
            if videos_in_dir:
                print(f'  -> Found {len(videos_in_dir)} Video files (e.g., {videos_in_dir[0]})')
                total_videos += len(videos_in_dir)

    print(f'\n[!] GRAND TOTAL: {total_images} Images, {total_videos} Videos discovered across all sessions.')
    
    if total_images == 344:
        print('  [+] EXACT MATCH with Dossier v22 (344 BEV frames confirmed).')
    elif total_images > 0:
        print(f'  [-] MISMATCH with Dossier. Expected 344, found {total_images}.')
    else:
        print('  [-] CRITICAL: No visual data found for the VLA model!')
else:
    print('[-] Sessions directory NOT FOUND.')

print('\n>>> ROUND 10 SCAN COMPLETE <<<')
