# Compliance Template

A compliance documentation workflow using [OSCAL](https://pages.nist.gov/OSCAL/) with [Trestle](https://github.com/IBM/compliance-trestle) to generate a System Security Plan (SSP) using Markdown.

## Usage

### Background

For a little background on OSCAL please see the [glossary](glossary.md) and [control families](control-families.md) documentation.

### Make

We use the Makefile for our workflow. You will be primarily working in [dist/system-security-plans/ato](dist/system-security-plans/ato) where all the Markdown for our controls live. You will usually not need to run any Make commands while documenting. Just add your explanation on each control to the SSP Markdown. But the Make commands we have are: 

- `make generate` to have `trestle` generate the corresponding control statement in Markdown. Use this if you need to add a control.
- `make generate-with-header` to have `trestle` generate the corresponding control statement in Markdown with the status headers.
- `make assemble` will generate the resulting OSCAL System Security Plan (SSP).
- `make status` will print out some basic metrics about control status bits.

### Suggested workflow

Here is a suggested compliance documentation workflow that uses [compliance-trestle](https://github.com/IBM/compliance-trestle):

- Add a control to the [profile](./profiles/ato/) that will be satisfied.
- Run `make generate` to have `trestle` generate the corresponding control statement in Markdown.
  - This Markdown file will live in `dist/system-security-plans/`.
- Flesh out implementation detail stubs for that control.
  - It is OK to leave a control implementation description blank initially.
  - Backfill missing implementation descriptions as needed.
  - If links to existing code are needed, consider linking to high level artifacts with a general description.
    - Avoid linking directly to lines of code as these will change over time.
- (Optionally) Run `make assemble` to generate the resulting OSCAL System Security Plan (SSP).
  - This is an optional step because nothing uses the OSCAL SSP yet.

### Status

To track compliance status, there's a header yaml file with a status list. The options are:

- `c-not-implemented`: this control has not been met or documented.
- `c-implemented`: this control has been met and documented.
- `c-inherited`: this control is inherited from cloud.gov or another system we use.
- `c-org-help-needed`: this control needs to be implemented at a higher level.

`make status` will print out some basic metrics about control status bits.

## Controls

Below are details about the controls, including additional parameters, notes, and control families.

### Parameters

A few controls require us to supply parameters to the control. These parameter choices are given in the official NIST catalog description. For instance, `sc-12.2` requires us to choose between `NIST FIPS-compliant` or `NSA-approved` symmetric keys.

To provide a parameter, edit the [profile](./profiles/ato/profile.json) and add the relevant parameter id to the `set-parameters` section, along with the value(s) that best fits the control. (Note that some controls allow more than one parameter.)

It is also possible to override the default parameters for a control, if needed.

Once new parameters are set in the profile, please run `make generate` to re-generate the control Markdown with the new parameters.

## Attribution

This is a copy with alternations from the 18F [compliance-template](https://github.com/GSA-TTS/compliance-template)

## Getting started for non-python devs

1. Install [pipenv](https://docs.pipenv.org/)
1. Run `pipenv install` to install dependencies from `Pipfile`
1. Run `pipenv shell` to start a shell with the correct virtual environment configured
