import os
import json
import time
import tempfile
import unittest
import hashlib
from chat_core import ChatConnector

class TestStaleClosure(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cc = ChatConnector(base_dir=self.tmp)
        self.workspace_hash = hashlib.md5(self.tmp.encode("utf-8")).hexdigest()[:8]

    def test_adversarial_stale_closure_simulation(self):
        print("\n=== STARTING ADVERSARIAL STALE-CLOSURE SIMULATION ===")
        
        # 1. Agent A writes a valid handoff receipt
        now = int(time.time())
        auth_file_path = os.path.join(self.tmp, "auth.py")
        
        # Create auth.py first
        with open(auth_file_path, "w") as f:
            f.write("# Agent A initial implementation\n")
            
        # Set modification time of auth.py to be older than the receipt
        os.utime(auth_file_path, (now - 100, now - 100))
        
        # Save handoff receipt
        print("[Agent A] Saving handoff receipt...")
        res = self.cc.save_handoff_receipt(
            obligations={"promise": "Implement Auth Logic", "scope": ["auth.py"]},
            work_state={"touched_surfaces": [{"file_path": "auth.py", "summary": "Setup auth", "why": "Initial setup"}], "dependencies": []},
            evidence={"checks_run": [{"command": "pytest auth_test.py", "exit_code": 0, "stdout_summary": "All tests passed"}], "missing_evidence": []},
            invalidation={
                "stale_if": [{"file_path": "auth.py"}],
                "next_safe_action": "Enable auth config"
            },
            status="open"
        )
        print(f"Receipt saved: {res}")
        
        # Verify initial state (should not be stale, but still blocked since status="open")
        state_initial = self.cc.get_workspace_handoff_state("default")
        self.assertTrue(state_initial["blocked"])
        # Since the status is open and not stale, original action is unchanged
        self.assertEqual(state_initial["next_safe_action"], "Enable auth config")
        print("[Agent A Handoff] Workspace status initially open/blocked with action:", state_initial["next_safe_action"])

        # 2. Agent B modifies the monitored auth file (stale_if path)
        print("[Agent B] Modifying monitored auth.py file...")
        with open(auth_file_path, "a") as f:
            f.write("# Agent B added OAuth support\n")
            
        # Force modification time of auth.py to be newer than the receipt
        os.utime(auth_file_path, (now + 100, now + 100))
        print(f"auth.py mtime set to: {now + 100} (receipt timestamp: {now})")

        # 3. Agent C boots and retrieves the workspace state (gets blocked by stale conditions)
        print("[Agent C] Resolving active receipt and validating staleness...")
        state_final = self.cc.get_workspace_handoff_state("default")
        
        # Verification assertions
        self.assertTrue(state_final["blocked"], "Workspace must be flagged as blocked")
        
        next_action = state_final["next_safe_action"]
        print(f"\n[Agent C Output] Mutated next_safe_action prompt:\n>>> {next_action}\n")
        
        # Check invalidating cause and re-observation mandate are present in next_safe_action
        self.assertIn("Blocked by stale/modified files", next_action)
        self.assertIn("auth.py", next_action)
        self.assertIn("Mandatory active re-observation required", next_action)
        
        print("=== ADVERSARIAL STALE-CLOSURE SIMULATION COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    unittest.main()
