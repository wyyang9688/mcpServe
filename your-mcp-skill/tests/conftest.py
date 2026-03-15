import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MCP_SERVER = ROOT / "mcp-server"
sys.path.insert(0, str(MCP_SERVER))

