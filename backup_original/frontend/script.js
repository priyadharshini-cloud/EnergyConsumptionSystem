
document.addEventListener("DOMContentLoaded", function () {

    // ==========================================
    // 1. DISPLAY CURRENT DATE
    // ==========================================

    const dateElement = document.getElementById("currentDate");

    if (dateElement) {
        dateElement.textContent = new Date().toLocaleDateString("en-IN", {
            day: "2-digit",
            month: "short",
            year: "numeric"
        });
    }


    // ==========================================
    // 2. METER READING CALCULATION
    // ==========================================

    const previousReading = document.getElementById("previousReading");
    const currentReading = document.getElementById("currentReading");
    const energyConsumed = document.getElementById("energyConsumed");

    function calculateConsumption() {
        if (!previousReading || !currentReading || !energyConsumed) {
            return;
        }

        const previous = parseFloat(previousReading.value);
        const current = parseFloat(currentReading.value);

        if (
            previousReading.value !== "" &&
            currentReading.value !== "" &&
            Number.isFinite(previous) &&
            Number.isFinite(current) &&
            previous >= 0 &&
            current >= previous
        ) {
            energyConsumed.value = (current - previous).toFixed(2);
        } else {
            energyConsumed.value = "";
        }
    }

    if (previousReading && currentReading) {
        previousReading.addEventListener("input", calculateConsumption);
        currentReading.addEventListener("input", calculateConsumption);
    }


    // ==========================================
    // 3. CONSUMPTION ANALYTICS CHART
    // ==========================================

    const chartCanvas = document.getElementById("consumptionChart");
    const chartPeriod = document.getElementById("chartPeriod");
    const chartPlaceholder = document.querySelector(".chart-placeholder");

    let consumptionChart = null;

    // Convert a date to YYYY-MM-DD using local time.
    function formatDateKey(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");

        return `${year}-${month}-${day}`;
    }

    async function loadConsumptionAnalytics() {
        if (!chartCanvas) {
            console.error("Consumption chart canvas was not found.");
            return;
        }

        if (typeof Chart === "undefined") {
            console.error("Chart.js is not loaded. Check index.html.");
            if (chartPlaceholder) {
                chartPlaceholder.textContent =
                    "Chart could not load. Please check your internet connection.";
                chartPlaceholder.style.display = "flex";
            }
            return;
        }

        const days = chartPeriod ? chartPeriod.value : "7";

        try {
            const response = await fetch(
                `/api/readings?days=${days}`
            );

            if (!response.ok) {
                if (response.status === 401) {
                    throw new Error("Please log in to view your readings.");
                }

                throw new Error("Could not load readings from the backend.");
            }

            const result = await response.json();
            const readings = result.readings || [];

            // Group energy consumption by date.
            const dailyTotals = {};

            readings.forEach(function (reading) {
                const dateKey = reading.reading_date;

                dailyTotals[dateKey] =
                    (dailyTotals[dateKey] || 0) +
                    Number(reading.energy_consumed);
            });

            // Create labels for the selected number of days.
            const labels = [];
            const values = [];
            const dateKeys = [];

            for (let i = Number(days) - 1; i >= 0; i--) {
                const date = new Date();
                date.setHours(12, 0, 0, 0);
                date.setDate(date.getDate() - i);

                const key = formatDateKey(date);

                dateKeys.push(key);

                labels.push(
                    date.toLocaleDateString("en-IN", {
                        day: "2-digit",
                        month: "short"
                    })
                );

                values.push(
                    Number((dailyTotals[key] || 0).toFixed(2))
                );
            }

            // Update the existing dashboard chart.
            if (consumptionChart) {
                consumptionChart.destroy();
            }

            consumptionChart = new Chart(chartCanvas, {
                type: "line",

                data: {
                    labels: labels,

                    datasets: [{
                        label: "Energy Consumed (kWh)",
                        data: values,
                        borderColor: "#16a085",
                        backgroundColor: "rgba(22, 160, 133, 0.15)",
                        borderWidth: 3,
                        fill: true,
                        tension: 0.35,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }]
                },

                options: {
                    responsive: true,
                    maintainAspectRatio: false,

                    interaction: {
                        intersect: false,
                        mode: "index"
                    },

                    plugins: {
                        legend: {
                            display: true,
                            position: "top"
                        },

                        tooltip: {
                            callbacks: {
                                label: function (context) {
                                    return (
                                        "Energy Consumed: " +
                                        context.parsed.y.toFixed(2) +
                                        " kWh"
                                    );
                                }
                            }
                        }
                    },

                    scales: {
                        y: {
                            beginAtZero: true,

                            title: {
                                display: true,
                                text: "Energy Consumption (kWh)"
                            }
                        },

                        x: {
                            title: {
                                display: true,
                                text: "Reading Date"
                            }
                        }
                    }
                }
            });

            // Hide the placeholder when the chart is ready.
            if (chartPlaceholder) {
                chartPlaceholder.style.display = "none";
            }

            // Update optional analytics summary elements if present.
            updateAnalyticsSummary(values, labels);

            console.log("Consumption analytics loaded successfully.");

        } catch (error) {
            console.error("Analytics error:", error);

            if (chartPlaceholder) {
                chartPlaceholder.textContent = error.message;
                chartPlaceholder.style.display = "flex";
            }

            const messageElement =
                document.getElementById("analyticsMessage");

            if (messageElement) {
                messageElement.textContent = error.message;
            }
        }
    }


    // ==========================================
    // 4. UPDATE ANALYTICS SUMMARY
    // ==========================================

    function updateAnalyticsSummary(values, labels) {
        const totalElement =
            document.getElementById("totalConsumption");

        const averageElement =
            document.getElementById("averageConsumption");

        const highestElement =
            document.getElementById("highestConsumption");

        const highestDateElement =
            document.getElementById("highestDate");

        const total = values.reduce(function (sum, value) {
            return sum + value;
        }, 0);

        const average = total / values.length;

        const highest = Math.max(...values);
        const highestIndex = values.indexOf(highest);

        if (totalElement) {
            totalElement.textContent = total.toFixed(2) + " kWh";
        }

        if (averageElement) {
            averageElement.textContent = average.toFixed(2) + " kWh";
        }

        if (highestElement) {
            highestElement.textContent = highest.toFixed(2) + " kWh";
        }

        if (highestDateElement) {
            highestDateElement.textContent =
                "Date: " + labels[highestIndex];
        }

        const messageElement =
            document.getElementById("analyticsMessage");

        if (messageElement) {
            messageElement.textContent =
                "Showing recorded consumption for the selected period.";
        }
    }


    // Reload chart when the user changes the period.
    if (chartPeriod) {
        chartPeriod.addEventListener("change", loadConsumptionAnalytics);
    }


    // ==========================================
    // 5. SAVE METER READING
    // ==========================================

    const readingForm = document.getElementById("readingForm");

    if (readingForm) {
        readingForm.addEventListener("submit", async function (event) {
            event.preventDefault();

            const dateInput = document.getElementById("readingDate");

            const date = dateInput ? dateInput.value : "";
            const previous = previousReading
                ? parseFloat(previousReading.value)
                : NaN;

            const current = currentReading
                ? parseFloat(currentReading.value)
                : NaN;

            if (
                !date ||
                !Number.isFinite(previous) ||
                !Number.isFinite(current)
            ) {
                alert("Please enter all meter reading details.");
                return;
            }

            if (previous < 0 || current < 0) {
                alert("Meter readings cannot be negative.");
                return;
            }

            if (current < previous) {
                alert(
                    "Current reading cannot be less than previous reading."
                );
                return;
            }

            try {
                const response = await fetch("/api/readings", {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json"
                    },

                    body: JSON.stringify({
                        reading_date: date,
                        previous_reading: previous,
                        current_reading: current
                    })
                });

                const result = await response.json();

                if (!response.ok) {
                    alert(result.error || "Could not save the reading.");
                    return;
                }

                alert(
                    "Reading saved successfully!\n\n" +
                    "Energy Consumed: " +
                    Number(result.energy_consumed).toFixed(2) +
                    " kWh"
                );

                readingForm.reset();

                if (energyConsumed) {
                    energyConsumed.value = "";
                }

                // Refresh analytics immediately after saving.
                await loadConsumptionAnalytics();

            } catch (error) {
                console.error("Save reading error:", error);

                alert(
                    "Could not connect to the backend. " +
                    "Please make sure Flask is running."
                );
            }
        });
    }


    // ==========================================
    // 6. LOAD ANALYTICS WHEN DASHBOARD OPENS
    // ==========================================

    loadConsumptionAnalytics();

});