generate-with-header:
	trestle author ssp-generate -p ato -o dist/system-security-plans/ato -y status_header.yaml

generate:
	trestle author ssp-generate -p ato -o dist/system-security-plans/ato

assemble:
	trestle author ssp-assemble --markdown dist/system-security-plans/ --output ato

status:
	grep -R "\- c\-" dist/system-security-plans/* | cut -d':' -f2 | sed -E 's/^.*(c-)/\1/' | sort | uniq -c
