# ACTP LeetCode-Style Test Repository

This repository contains 5 small coding-agent tasks. Each task has:
- `problem.md` — task specification
- `solution.py` — intentionally incomplete implementation
- `test_solution.py` — pytest tests

## Tasks

1. Two Sum
2. Valid Parentheses
3. Binary Search
4. Best Time to Buy and Sell Stock
5. Maximum Subarray

The intended experiment is:

    problem -> ACTP -> inspect -> edit -> test -> observe -> replan -> verify

The implementations are deliberately incomplete, so the tests should initially fail.

## Run one task manually

    cd 01_two_sum
    python3 -m pytest -q

## Run all tasks manually

From this repository root:

    for d in 01_* 02_* 03_* 04_* 05_*; do
      (cd "$d" && python3 -m pytest -q) || true
    done

## ACTP task prompts

Use the exact prompts from `RUN_ACTP.md`.
