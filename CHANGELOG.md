# Changelog
All notable changes to this project will be documented in this file.

## [0.2.9](https://github.com/JCapriotti/dynamodb-session-web/tree/v0.2.9) - 2022-11-13

### Updated

- Allow package to be installed on Python >= 3.7; previously was >= 3.9, for no reason.
- Improved `tox` file for quicker runs and conciseness.
- Added explicit `Optional` to some method arguments; where before it was implicit.

## [0.2.8](https://github.com/JCapriotti/dynamodb-session-web/tree/v0.2.8) - 2022-09-09

### Added

- Allow a `region_name` parameter to be used when creating SessionManager instance, 
  which is passed to the internal `boto3` resource.

## Older

Nothing significant to mention
