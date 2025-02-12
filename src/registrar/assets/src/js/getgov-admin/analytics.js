import { debounce } from '../getgov/helpers.js';
import { getParameterByName } from './helpers-admin.js';

/** This function also sets the start and end dates to match the url params if they exist
*/
function initAnalyticsExportButtons() {
    // Get the current date in the format YYYY-MM-DD
    let currentDate = new Date().toISOString().split('T')[0];

    // Default the value of the start date input field to the current date
    let startDateInput = document.getElementById('start');

    // Default the value of the end date input field to the current date
    let endDateInput = document.getElementById('end');

    let exportButtons = document.querySelectorAll('.exportLink');

    if (exportButtons.length > 0) {
        // Check if start and end dates are present in the URL
        let urlStartDate = getParameterByName('start_date');
        let urlEndDate = getParameterByName('end_date');

        // Set input values based on URL parameters or current date
        startDateInput.value = urlStartDate || currentDate;
        endDateInput.value = urlEndDate || currentDate;

        exportButtons.forEach((btn) => {
            btn.addEventListener('click', function () {
                // Get the selected start and end dates
                let startDate = startDateInput.value;
                let endDate = endDateInput.value;
                let exportUrl = btn.dataset.exportUrl;

                // Build the URL with parameters
                exportUrl += "?start_date=" + startDate + "&end_date=" + endDate;

                // Redirect to the export URL
                window.location.href = exportUrl;
            });
        });
    }
};

/**
     * Creates a diagonal stripe pattern for chart.js
     * Inspired by https://stackoverflow.com/questions/28569667/fill-chart-js-bar-chart-with-diagonal-stripes-or-other-patterns
     * and https://github.com/ashiguruma/patternomaly
     * @param {string} backgroundColor - Background color of the pattern
     * @param {string} [lineColor="white"] - Color of the diagonal lines
     * @param {boolean} [rightToLeft=false] - Direction of the diagonal lines
     * @param {number} [lineGap=1] - Gap between lines
     * @returns {CanvasPattern} A canvas pattern object for use with backgroundColor
     */
function createDiagonalPattern(backgroundColor, lineColor, rightToLeft=false, lineGap=1) {
    // Define the canvas and the 2d context so we can draw on it
    let shape = document.createElement("canvas");
    shape.width = 20;
    shape.height = 20;
    let context = shape.getContext("2d");

    // Fill with specified background color
    context.fillStyle = backgroundColor;
    context.fillRect(0, 0, shape.width, shape.height);

    // Set stroke properties
    context.strokeStyle = lineColor;
    context.lineWidth = 2;

    // Rotate canvas for a right-to-left pattern
    if (rightToLeft) {
        context.translate(shape.width, 0);
        context.rotate(90 * Math.PI / 180);
    };

    // First diagonal line
    let halfSize = shape.width / 2;
    context.moveTo(halfSize - lineGap, -lineGap);
    context.lineTo(shape.width + lineGap, halfSize + lineGap);

    // Second diagonal line (x,y are swapped)
    context.moveTo(-lineGap, halfSize - lineGap);
    context.lineTo(halfSize + lineGap, shape.width + lineGap);

    context.stroke();
    return context.createPattern(shape, "repeat");
}

function createComparativeColumnChart(id, title, labelOne, labelTwo) {
    var canvas = document.getElementById(id);
    if (!canvas) {
        return
    }

    var ctx = canvas.getContext("2d");
    var listOne = JSON.parse(canvas.getAttribute('data-list-one'));
    var listTwo = JSON.parse(canvas.getAttribute('data-list-two'));

    var data = {
        labels: ["Total", "Federal", "Interstate", "State/Territory", "Tribal", "County", "City", "Special District", "School District", "Election Board"],
        datasets: [
            {
                label: labelOne,
                backgroundColor: "rgba(255, 99, 132, 0.3)",
                borderColor: "rgba(255, 99, 132, 1)",
                borderWidth: 1,
                data: listOne,
                // Set this line style to be rightToLeft for visual distinction
                backgroundColor: createDiagonalPattern('rgba(255, 99, 132, 0.3)', 'white', true)
            },
            {
                label: labelTwo,
                backgroundColor: "rgba(75, 192, 192, 0.3)",
                borderColor: "rgba(75, 192, 192, 1)",
                borderWidth: 1,
                data: listTwo,
                backgroundColor: createDiagonalPattern('rgba(75, 192, 192, 0.3)', 'white')
            },
        ],
    };

    var options = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
            },
            title: {
                display: true,
                text: title
            }
        },
        scales: {
            y: {
                beginAtZero: true,
            },
        },
    };
    return new Chart(ctx, {
        type: "bar",
        data: data,
        options: options,
    });
}

/** An IIFE to initialize the analytics page
*/
export function initAnalyticsDashboard() {
    const analyticsPageContainer = document.querySelector('.analytics-dashboard .analytics-dashboard-charts');
    if (analyticsPageContainer) {
        document.addEventListener("DOMContentLoaded", function () {
            initAnalyticsExportButtons();

            // Create charts and store each instance of it
            const chartInstances = new Map();
            const charts = [
                { id: "managed-domains-chart", title: "Managed domains" },
                { id: "unmanaged-domains-chart", title: "Unmanaged domains" },
                { id: "deleted-domains-chart", title: "Deleted domains" },
                { id: "ready-domains-chart", title: "Ready domains" },
                { id: "submitted-requests-chart", title: "Submitted requests" },
                { id: "all-requests-chart", title: "All requests" }
            ];
            charts.forEach(chart => {
                if (chartInstances.has(chart.id)) chartInstances.get(chart.id).destroy();
                let chart = createComparativeColumnChart(...chart, "Start Date", "End Date");
                chartInstances.set(chart.id, chart);
            });

            // Add resize listener to each chart
            window.addEventListener("resize", debounce(() => {
                chartInstances.forEach((chart) => {
                    if (chart?.canvas) chart.resize();
                });
            }, 200));
        });
    }
};
