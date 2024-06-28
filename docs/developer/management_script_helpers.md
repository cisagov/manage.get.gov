# Terminal Helper Functions
`terminal_helper.py` contains utility functions to assist with common terminal and script operations. 
This file documents what they do and provides guidance on their usage.

## TerminalColors
`TerminalColors` provides ANSI color codes as variables to style terminal output.

## ScriptDataHelper
### bulk_update_fields

`bulk_update_fields` performs a memory-efficient bulk update on a Django model in batches using a Paginator.

## TerminalHelper
### log_script_run_summary

`log_script_run_summary` logs a summary of a script run, including counts of updated, skipped, and failed records.

### print_conditional 

`print_conditional` conditionally logs a statement at a specified severity if a condition is met.

### prompt_for_execution

`prompt_for_execution` prompts the user to inspect a string and confirm if they wish to proceed. Returns True if proceeding, False if skipping, or exits the script.

### query_yes_no

`query_yes_no` prompts the user with a yes/no question and returns True for "yes" or False for "no".

### query_yes_no_exit

`query_yes_no_exit` is similar to `query_yes_no` but includes an "exit" option to terminate the script.

## PopulateScriptTemplate

`PopulateScriptTemplate` is an abstract base class that provides a template for creating generic populate scripts. It handles logging and bulk updating for repetitive scripts that update a few fields. 

### **Disclaimer** 
This template is intended as a shorthand for simple scripts. It is not recommended for complex operations. See `transfer_federal_agency.py` for a straightforward example of how to use this template.

### Step-by-step usage guide
To create a script using `PopulateScriptTemplate`:
1. Create a new class that inherits from `PopulateScriptTemplate`
2. Implement the `update_record` method to define how each record should be updated
3. Optionally, override the configuration variables and helper methods as needed
4. Call `mass_update_records` within `handle` and run the script

#### Template explanation

The main method provided by `PopulateScriptTemplate` is `mass_update_records`. This method loops through each valid object (specified by `filter_conditions`) and updates the fields defined in `fields_to_update` using the `update_record` method.

Before updating, `mass_update_records` prompts the user to confirm the proposed changes. If the user does not proceed, the script will exit.

After processing the records, `mass_update_records` performs a bulk update on the specified fields using `ScriptDataHelper.bulk_update_fields` and logs a summary of the script run using `TerminalHelper.log_script_run_summary`.

#### Config options
The class provides the following optional configuration variables:
- `prompt_title`: The header displayed by `prompt_for_execution` when the script starts (default: "Do you wish to proceed?")
- `display_run_summary_items_as_str`: If True, runs `str(item)` on each item when printing the run summary for prettier output (default: False)
- `run_summary_header`: The header for the script run summary printed after the script finishes (default: None)

The class also provides helper methods:
- `get_class_name`: Returns a display-friendly class name for the terminal prompt
- `get_failure_message`: Returns the message to display if a record fails to update
- `should_skip_record`: Defines the condition for skipping a record (by default, no records are skipped)