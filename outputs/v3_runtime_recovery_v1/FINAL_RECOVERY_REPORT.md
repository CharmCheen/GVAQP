# Final Runtime / Config Recovery Report

1. **V7 frozen runtime:** semantic processor identity is exactly recovered from V7: Python 3.13.2, torch 2.10.0+cu129, transformers 5.9.0, qwen-vl-utils 0.0.14, NumPy 2.4.6, Pillow 12.1.1, OpenCV 4.13.0.
2. **Current difference:** transformers 5.5.4, NumPy 2.2.6, OpenCV 5.0.0 differ; the other four identity fields match.
3. **Output impact:** these three are output-critical by V7's own gate, but three cross-video processor tensor checks matched exactly. Generation semantics remain unverified without loading the model.
4. **Runtime reconstruction:** the processor identity can be specified locally; a complete dependency lock cannot be reconstructed because no V7 lock/pip-freeze/container digest exists.
5. **Old processor:** the sealed runner requires its identity strings; current processor behavior is compatible on checked inputs but cannot bypass that gate.
6. **Scan config:** DALI/HANGZHOU/WUHAN do not have a frozen V3 scan configuration.
7. **Scan execution:** it was never run under V3; it was not merely missing finalization.
8. **Remaining compute:** V7 oracle remains 1,475 fresh calls (V7 estimate 16.593 A100 GPU-hours); V3 scan/proxy unit count/config/cost is unknown because no contract exists.
9. **User input:** required only for the missing frozen V3 scan/proxy contract, not for model identity or source videos.
10. **Resume:** no; reference release cannot legally resume until that contract is provided/authorized.
