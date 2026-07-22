# Baseline equality audit

`mean(d1)=11.056640625`, `mean(d2)=11.056640625`, and `mean(d3)=0.000000000`. The maximum absolute difference `|d1-d2|` is 0; all 512 π0/B2-K1 utilities and all 512 action sequences are exactly equal.

**Conclusion A:** π0 and B2-K1 are episode-wise strategy-equivalent in this implementation. B2-K1 chooses a confirmation after every scan, reproducing π0's FIFO-confirm-then-scan behavior. The best-simple comparator is selected globally by frozen primary-utility macro mean, never per episode.
