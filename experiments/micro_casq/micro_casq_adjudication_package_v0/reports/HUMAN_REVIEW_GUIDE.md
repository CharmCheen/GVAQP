# Human Review Guide

## Goal

Determine whether each pilot clip contains `O_enter_ego_path_v0`.

## Positive Criteria

A road user enters or clearly overlaps the ego vehicle's future driving path and creates potential spatial conflict or requires ego attention.

## Negative Examples

- normal following traffic
- dense traffic with no identifiable entering event
- static roadside objects
- far-away crossing without ego-path conflict
- parked vehicles with no motion into ego path
- low-speed irrelevant maneuvers
- poor/irrelevant view

## Allowed Review Labels

- `positive`
- `negative`
- `abstain`

## Required Boundary Fields For Positive

- `event_start`
- `event_end`
- `boundary_status`

## Boundary Status

- `ok`
- `uncertain`
- `truncated`
- `not_applicable`

## Provenance Warnings

Old labels are only provenance. They are not gold truth.

Nexar-derived labels are noisy external labels.

VLM-derived labels are not human truth.

Human reviewer should judge against `O_enter_ego_path_v0`, not against `old_label`.
