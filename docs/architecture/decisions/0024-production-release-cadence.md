# 24. Production Release Cadence

Date: 2023-11-02

## Status

In Review

## Context

Going into our first production launch we need a plan describing what our release cadence for both our staging and stable envirornments will be. Currently, we release to staging whenever there are significant changes made, but we have not been making releases to stable with the same frequency.

## Considered Options

**Option 1:** Releasing to stable/staging once a sprint
Releasing once a sprint would mean that we release the past sprint's work to stable at the end of the current sprint. At the same point, the current sprint's work would be pushed to staging, thus making staging a full sprint ahead of stable. While this is more straight forward, it means our users would have to wait longer to see changes that weren't deemed critical.
**Option 2:** Releasing to stable/staging once a week
Releasing once a week would follow the same flow but with code being released to staging one week before the same code is released to stable. This would make stable only one week behind staging and would allow us to roll out minor bug fixes faster. The negative side is that we have less time to see if errors occur on staging.

In both of the above scenarios, the release date would fall on the same day of the week that the sprint starts which is currently a Wednesday. Additionally, in both scenarios the release commits would eventually be tagged with both a staging and stable tag. Furthermore, critical bugs or features would be exempt from these restrictions based on the product owner's discretion.

## Decision

We decided to go with option 2 and release once a week once in production. This will allow us to give users features and bug fixes faster while still allowing enough time on staging for quality to be maintained.

## Consequences

Work not completed by end of the sprint will have to wait to be added to stable. Also, making quick fixes for bugs that are found on stable will be a little more complicated.

When first going into production, staging and stable will start with the same code base. The following week a new release will be made to staging, but not stable as no code will have been on staging long enough to warrant another release. Thus just at the start of launch stable will be essentially frozen for 2 weeks, not one.
