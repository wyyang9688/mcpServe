#!/usr/bin/env python3
"""
OpenClaw WeChat MP - Publish End to End Script
Direct script execution mode for reliable operation.
"""

import sys
import os
import argparse
import asyncio
import json

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    parser = argparse.ArgumentParser(description='OpenClaw WeChat MP Publish Script')
    parser.add_argument('--title', type=str, required=True, help='Article title')
    parser.add_argument('--author', type=str, default='', help='Article author')
    parser.add_argument('--content-file', type=str, required=True, help='Path to HTML content file')
    parser.add_argument('--cover-path', type=str, required=True, help='Path to cover image file')
    parser.add_argument('--channel', type=str, default='chrome', help='Browser channel')
    parser.add_argument('--headless', type=lambda x: x.lower() == 'true', default=False, help='Run in headless mode')
    parser.add_argument('--slow_mo_ms', type=int, default=200, help='Slow motion delay in milliseconds')
    parser.add_argument('--executable_path', type=str, default=None, help='Browser executable path')
    
    args = parser.parse_args()
    
    try:
        # Read content file
        with open(args.content_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        from openclaw_wechat_mcp.server import publish_end_to_end
        
        class MockContext:
            async def info(self, msg):
                print(f"INFO: {msg}")
            
            async def error(self, msg):
                print(f"ERROR: {msg}")
            
            async def report_progress(self, elapsed, total, message):
                print(f"PROGRESS: {elapsed}/{total} - {message}")
        
        ctx = MockContext()
        
        async def run_publish():
            result = await publish_end_to_end(
                ctx,
                title=args.title,
                author=args.author,
                content=content,
                cover_path=args.cover_path,
                channel=args.channel,
                headless=args.headless,
                slow_mo_ms=args.slow_mo_ms,
                executable_path=args.executable_path
            )
            print("Publish result:", json.dumps(result, indent=2, ensure_ascii=False))
            return result
        
        result = asyncio.run(run_publish())
        
        # Exit with appropriate code
        if result.get('structuredContent', {}).get('ok', False):
            sys.exit(0)  # Success
        else:
            sys.exit(1)  # Failed
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()