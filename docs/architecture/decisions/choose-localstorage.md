# Local Game Storage Architecture Decision

## Status

Proposed

## Context

Storing user game data. 

## Decision

Store user game data in local storage of the browser rather than designing and implementing a full database.

## Consequences

### Pros
* Game data storage becomes easier

### Cons
* There is no game data sync to different browsers 
* Clearing cache and data clears their game data