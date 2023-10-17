let myChart; // Declare a variable to store the chart instance

document.addEventListener('DOMContentLoaded', function() {

    const form = document.getElementById('chartCustomTimeline');
    form.addEventListener('submit', handleCustomTimeline);

    const frequencyButtons = document.querySelectorAll('.chart-frequency');
    frequencyButtons.forEach(button => {
        button.addEventListener('click', async () => {
            console.log(`Event listener triggered. ${myChart}`);
            await updateChart(myChart);
        });
    })
});

// Setting the chart
function chartInitialization(type, chartData) {
    const ctxChart = document.getElementById(`${type}BarChart`);
    myChart = new Chart(ctxChart, {
        type: 'bar',
        data: {
            labels: chartData.labels,
            datasets: [{
                data: chartData.data,
                datalabels: {
                    anchor: 'end',
                    align: 'top',
                    offset: 5,
                }
            }]
        },
        plugins: [ChartDataLabels],
        options: {
            responsive: true,
            aspectRatio: 1|3,
            scales: {
                x: {
                    stacked: true,
                    grid: {
                        display: false
                    }
                },
                y: {
                    grace: '5%',
                    stacked: true,
                    title: {
                        display: true,
                        text: chartData.currency,
                    },
                    grid: {
                        display: false
                    }
                },
            },
            layout: {
                padding: 20
            },
            plugins: {
                legend: {
                    display: false, // Hide the legend
                },
            },
        },
    });
}

// Handling changing the timeline of the chart. Function referenced directly in timeline-chart.html
function changeTimeline(element) {

    const toDate = new Date(document.getElementById('chartDateTo').value);
    let fromDate;

    switch (element.value) {
        case 'YTD':
            fromDate = new Date(new Date().getFullYear(), 0, 1);
            break;
        case '3m':
            fromDate = new Date(toDate.getFullYear(), toDate.getMonth() - 3, toDate.getDate());
            break;
        case '6m':
            fromDate = new Date(toDate.getFullYear(), toDate.getMonth() - 6, toDate.getDate());
            break;
        case '12m':
            fromDate = new Date(toDate.getFullYear(), toDate.getMonth() - 12, toDate.getDate());
            break;
        case '3Y':
            fromDate = new Date(toDate.getFullYear() - 3, toDate.getMonth(), toDate.getDate());
            break;
        case '5Y':
            fromDate = new Date(toDate.getFullYear() - 5, toDate.getMonth(), toDate.getDate());
            break;
        case 'All':
            fromDate = new Date('2000-01-01');
            break;
        case 'Custom':
            let myModal = new bootstrap.Modal(document.getElementById('modalChartTimeline'), {});
            myModal.show();
            break;
    }

    if (element.value != "Custom") {
        document.getElementById('chartDateFrom').value = convertDate(fromDate);
        updateChart(myChart);
    }
}

// Convert to YYYY-mmm-dd format
function convertDate(date) {
    let day = ("0" + date.getDate()).slice(-2);
    let month = ("0" + (date.getMonth() + 1)).slice(-2);
    console.log(day, month);
    return date.getFullYear()+"-"+(month)+"-"+(day);
}

// Handling click of custom timeline modal
function handleCustomTimeline(event) {
    event.preventDefault();

    // Close the Modal
    const modalReference = document.getElementById("modalChartTimeline");
    const timelineModal = bootstrap.Modal.getInstance(modalReference);
    timelineModal.hide();

    updateChart(myChart);

}

function getChartData(type, elementId, frequency, from, to) {

    return fetch(`/get_chart_data?type=${type}&id=${elementId}&frequency=${frequency}&from=${from}&to=${to}`)
        .then(response => response.json())
        .then(chartData => {
            return chartData;
        })
        .catch(error => {
            console.error('Error fetching chart data:', error);
            return null;
        });
}

async function updateChart(chart) {

    // Get the current URL path
    const path = window.location.pathname;
            
    // Extract the type from the path
    const match = path.match(/^\/(properties|tenants|transactions)\/?/);
    let type = match ? match[1] : null;

    // Convert plural form to singular
    if (type) {
        if (type === 'properties') {
            type = 'property';
        } else {
            type = type.slice(0, -1);
        }
    }

    const elementId = document.getElementById("deleteButton").getAttribute(`data-${type}-id`)
    const frequency = document.querySelector('input[name="chartFrequency"]:checked').value;
    const from = document.getElementById("chartDateFrom").value;
    const to = document.getElementById("chartDateTo").value;
    const chartData = await getChartData(type, elementId, frequency, from, to);

    chart.data.labels = chartData.labels;
    chart.data.datasets[0].data = chartData.data;
    chart.update();

}