#!/usr/bin/env python3
"""
OpenClaw WeChat MP - Login and Wait Script
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
    parser = argparse.ArgumentParser(description='OpenClaw WeChat MP Login Script')
    parser.add_argument('--timeout_ms', type=int, default=300000, help='Login timeout in milliseconds')
    parser.add_argument('--poll_ms', type=int, default=1000, help='Polling interval in milliseconds')
    parser.add_argument('--headless', type=lambda x: x.lower() == 'true', default=False, help='Run in headless mode')
    parser.add_argument('--slow_mo_ms', type=int, default=200, help='Slow motion delay in milliseconds')
    parser.add_argument('--channel', type=str, default='chrome', help='Browser channel')
    parser.add_argument('--executable_path', type=str, default=None, help='Browser executable path')
    
    args = parser.parse_args()
    
    try:
        from openclaw_wechat_mcp.server import login_and_wait
        
        class MockContext:
            async def info(self, msg):
                print(f"INFO: {msg}")
            
            async def error(self, msg):
                print(f"ERROR: {msg}")
            
            async def report_progress(self, elapsed, total, message):
                print(f"PROGRESS: {elapsed}/{total} - {message}")
        
        ctx = MockContext()
        
        async def run_login():
            result = await login_and_wait(
                ctx,
                timeout_ms=args.timeout_ms,
                poll_ms=args.poll_ms,
                headless=args.headless,
                slow_mo_ms=args.slow_mo_ms,
                channel=args.channel,
                executable_path=args.executable_path
            )
            print("Login result:", json.dumps(result, indent=2, ensure_ascii=False))
            return result
        
        result = asyncio.run(run_login())
        
        # Exit with appropriate code
        if result.get('structuredContent', {}).get('logged_in', False):
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