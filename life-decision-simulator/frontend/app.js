/**
 * Life Decision Simulator - Frontend Application
 */

async function submitSimulation() {
    // Collect form data
    const profileData = {
        name: document.getElementById('name').value,
        age: parseInt(document.getElementById('age').value),
        education_level: document.getElementById('education').value,
        current_field: document.getElementById('current_field').value,
    };

    const decisionData = {
        description: document.getElementById('decision_description').value,
        decision_type: document.getElementById('decision_type').value,
    };

    // Validate input
    if (!profileData.name || !profileData.age || !decisionData.description) {
        alert('Please fill in all required fields');
        return;
    }

    try {
        // Send to backend
        const response = await fetch('/api/simulate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                profile: profileData,
                decision: decisionData,
            }),
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        const results = await response.json();
        displayResults(results);
    } catch (error) {
        console.error('Error:', error);
        alert('Error running simulation: ' + error.message);
    }
}

function displayResults(results) {
    const resultsDiv = document.getElementById('results');
    const resultsContent = document.getElementById('resultsContent');
    
    resultsContent.textContent = JSON.stringify(results, null, 2);
    resultsDiv.style.display = 'block';
    
    // Scroll to results
    resultsDiv.scrollIntoView({ behavior: 'smooth' });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Life Decision Simulator initialized');
});
