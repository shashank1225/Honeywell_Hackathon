# AABOS demonstration evidence

`AABOS_PoC_Demonstration.mp4` is the primary proof-of-concept recording. The
hackathon limits the PoC video to three minutes, so the screenshots below are
included as concise supplementary evidence for parts of the same live run that
could not be shown without exceeding that limit. They do not replace the live
closed-loop demonstration.

## What the screenshots show

1. **`01_llm_policy_accepted.png`** — the local Llama 3.2 recommendation is
   accepted by the Safety Sentinel and becomes the selected `energy_saver`
   policy. It also shows the advisory counterfactual comparison.
2. **`02_llm_policy_proposed.png`** — the strategic layer proposes a 24 °C,
   35% ventilation energy-saving policy after using the governed MCP tools
   `inspect_building_runtime` and `queue_policy_recommendation`.
3. **`03_energy_savings_and_safety_rejection.png`** — 19.01% measured energy
   savings are shown while a comfort-first recommendation is rejected for an
   excessive ventilation change and control-oscillation protection. The last
   known safe setpoints are retained.
4. **`04_comfort_policy_and_mcp_audit.png`** — a comfort-first local Llama
   policy, its MCP-tool audit, and the active runtime setpoints are visible.

Together with the video, these captures show both paths required for a
safety-governed autonomous loop: an approved policy is applied to the next
EnergyPlus cycle, while an unsafe policy is rejected and safely recovered.
