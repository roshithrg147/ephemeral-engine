#!/usr/bin/env python3
import sys
import unittest
import time
import json
from datetime import datetime

def main():
    print("="*60)
    print("EPHEMERAL ENGINE CONSOLIDATED TEST SUITE RUNNER")
    print("="*60)
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z\n")
    
    loader = unittest.TestLoader()
    # Discover all tests in src/tests
    suite = loader.discover('src/tests', pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    start_time = time.time()
    result = runner.run(suite)
    duration = time.time() - start_time
    
    print("\n" + "="*60)
    print("TEST EXECUTION SUMMARY")
    print("="*60)
    print(f"Total Tests Run: {result.testsRun}")
    print(f"Successful: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Duration: {duration:.3f} seconds")
    print("="*60)
    
    # Compile JSON report
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tests_run": result.testsRun,
        "success_count": result.testsRun - len(result.failures) - len(result.errors),
        "failures_count": len(result.failures),
        "errors_count": len(result.errors),
        "duration_seconds": duration,
        "status": "PASSED" if result.wasSuccessful() else "FAILED",
        "details": []
    }
    
    for failure in result.failures:
        report["details"].append({
            "test_case": str(failure[0]),
            "status": "FAILURE",
            "message": failure[1]
        })
        
    for error in result.errors:
        report["details"].append({
            "test_case": str(error[0]),
            "status": "ERROR",
            "message": error[1]
        })
        
    with open("consolidated_test_report.json", "w") as f:
        json.dump(report, f, indent=2)
        
    print("\nSaved consolidated report to: consolidated_test_report.json")
    
    if not result.wasSuccessful():
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
