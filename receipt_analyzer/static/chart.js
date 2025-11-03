function createChart(receipts) {
    const categoryTotals = {};
    let overallTotal = 0;

    receipts.forEach(receipt => {
        const category = receipt.category || 'Uncategorized';
        // Backend sends numeric string (e.g., "12.34"); be robust to currency symbols
        const totalString = typeof receipt.total === 'string' ? receipt.total : String(receipt.total ?? '0');
        const total = parseFloat(totalString.replace(/[^\d.-]/g, ''));

        if (!isNaN(total)) {
            if (category in categoryTotals) {
                categoryTotals[category] += total;
            } else {
                categoryTotals[category] = total;
            }
            overallTotal += total;
        }
    });

    const categoryLabels = Object.keys(categoryTotals);
    const categoryData = Object.values(categoryTotals);

    const ctx = document.getElementById('categoryChart').getContext('2d');
    new Chart(ctx, {
        type: 'pie',
        data: {
            labels: categoryLabels,
            datasets: [{
                data: categoryData,
                backgroundColor: [
                    '#FF6384',
                    '#36A2EB',
                    '#FFCE56',
                    '#4BC0C0',
                    '#9966FF',
                    '#FF9F40'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });

    const categoryTotalsList = document.getElementById('categoryTotals');
    categoryTotalsList.innerHTML = '';
    for (const [category, total] of Object.entries(categoryTotals)) {
        const listItem = document.createElement('li');
        listItem.textContent = `${category}: $${total.toFixed(2)}`;
        categoryTotalsList.appendChild(listItem);
    }

    document.getElementById('overallTotal').textContent = `$${overallTotal.toFixed(2)}`;
}
