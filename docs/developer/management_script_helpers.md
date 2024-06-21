# Terminal Helper Functions
`terminal_helper.py` contains utility functions to assist with common terminal and script operations. 
This file documents what they do and provides guidance on their usage.

## TerminalColors
`TerminalColors` provides ANSI color codes as variables to style terminal output.

Usage:
```print(f"{TerminalColors.OKGREEN}Success!{TerminalColors.ENDC}")```

## ScriptDataHelper
### bulk_update_fields

`bulk_update_fields` performs a memory-efficient bulk update on a Django model in batches using a Paginator.

Usage:
```bulk_update_fields(Domain, object_list, ["first_ready"])```

## TerminalHelper
### log_script_run_summary

`log_script_run_summary` logs a summary of a script run, including counts of updated, skipped, and failed records.

Usage:
```TerminalHelper.log_script_run_summary(self.to_update, self.failed_to_update, self.skipped, debug)```

### print_conditional 

`print_conditional` conditionally logs a statement at a specified severity if a condition is met.

Usage:
```python
TerminalHelper.print_conditional(
    debug_on,
    f"""{TerminalColors.YELLOW}Missing Domain Information
    {TerminalColors.ENDC}""",
)
```

### prompt_for_execution

`prompt_for_execution` prompts the user to inspect a string and confirm if they wish to proceed. Returns True if proceeding, False if skipping, or exits the script.

```python
TerminalHelper.prompt_for_execution(
    system_exit_on_terminate=True,
    info_to_inspect=f"""
    ==Master data file==
    domain_additional_filename: {org_args.domain_additional_filename}

    ==Organization data==
    organization_adhoc_filename: {org_args.organization_adhoc_filename}

    ==Containing directory==
    directory: {org_args.directory}
    """,
    prompt_title="Do you wish to load organization data for TransitionDomains?",
)
```

### query_yes_no

`query_yes_no` prompts the user with a yes/no question and returns True for "yes" or False for "no".

Usage:
```python
if query_yes_no("Do you want to proceed?"):
    print("Proceeding...")
else:
    print("Aborting.")
```

### query_yes_no_exit

`query_yes_no_exit` is similar to `query_yes_no` but includes an "exit" option to terminate the script.

Usage: 
if query_yes_no_exit("Continue, abort, or exit?"):
    print("Continuing...")
else:
    print("Aborting.")
    # Script will exit if user selected "e" for exit

## PopulateScriptTemplate

`PopulateScriptTemplate` is an abstract base class that provides a template for creating generic populate scripts. It handles logging and bulk updating for repetitive scripts that update a few fields. 

**Disclaimer:** This template is intended as a shorthand for simple scripts. It is not recommended for complex operations. See `transfer_federal_agency.py` for a straightforward example of how to use this template.

To use `PopulateScriptTemplate`, create a new class that inherits from it and implement the `update_record` method. This method defines how each record should be updated.

The class provides the following optional configuration variables:
- `prompt_title`: The header displayed by `prompt_for_execution` when the script starts (default: "Do you wish to proceed?")
- `display_run_summary_items_as_str`: If True, runs `str(item)` on each item when printing the run summary for prettier output (default: False)
- `run_summary_header`: The header for the script run summary printed after the script finishes (default: None)

The main method provided by `PopulateScriptTemplate` is `mass_update_records`. This method loops through each valid object (specified by `filter_conditions`) and updates the fields defined in `fields_to_update` using the `update_record` method.

Before updating, `mass_update_records` prompts the user to confirm the proposed changes. If the user does not proceed, the script will exit.

After processing the records, `mass_update_records` performs a bulk update on the specified fields using `ScriptDataHelper.bulk_update_fields` and logs a summary of the script run using `TerminalHelper.log_script_run_summary`.

The class also provides helper methods:
- `get_class_name`: Returns a display-friendly class name for the terminal prompt
- `get_failure_message`: Returns the message to display if a record fails to update
- `should_skip_record`: Defines the condition for skipping a record (by default, no records are skipped)

To create a script using `PopulateScriptTemplate`:
1. Create a new class that inherits from `PopulateScriptTemplate`
2. Implement the `update_record` method to define how each record should be updated
3. Optionally, override the configuration variables and helper methods as needed
4. Call `mass_update_records` within `handle` and run the script