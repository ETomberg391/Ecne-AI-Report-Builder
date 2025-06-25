document.addEventListener('DOMContentLoaded', function() {
    const apiKeyForm = document.getElementById('api-keys-form');
    const llmSettingsForm = document.getElementById('llm-settings-form');
    const llmModelSelect = document.getElementById('llm-model-select');
    const llmModelDetails = document.getElementById('llm-model-details');
    const newLlmModelDetails = document.getElementById('new-llm-model-details');
    const deleteLlmModelButton = document.getElementById('delete-llm-model');
    const saveLlmSettingsButton = document.getElementById('save-llm-settings');

    // Store loaded LLM settings to avoid re-fetching
    let currentLlmSettingsData = {};

    // --- Load Settings on Page Load ---
    async function loadSettings() {
        try {
            const response = await fetch('/api/settings');
            const data = await response.json();

            // Populate API Keys form
            if (data.api_keys) {
                document.getElementById('google_api_key').value = data.api_keys.GOOGLE_API_KEY || '';
                document.getElementById('google_cse_id').value = data.api_keys.GOOGLE_CSE_ID || '';
                document.getElementById('brave_api_key').value = data.api_keys.BRAVE_API_KEY || '';
                // Removed Reddit API fields as per requirements
            }

            // Populate LLM Models dropdown
            if (data.llm_settings) {
                currentLlmSettingsData = data.llm_settings; // Store for later use
                llmModelSelect.innerHTML = '<option value="">-- Select a model --</option>';
                for (const key in data.llm_settings) {
                    const option = document.createElement('option');
                    option.value = key;
                    option.textContent = key;
                    llmModelSelect.appendChild(option);
                }
                // Add "New LLM" option at the end
                const newLlmOption = document.createElement('option');
                newLlmOption.value = 'new-llm';
                newLlmOption.textContent = 'New LLM';
                llmModelSelect.appendChild(newLlmOption);
            }

            // Hide both detail sections initially
            llmModelDetails.style.display = 'none';
            newLlmModelDetails.style.display = 'none';

        } catch (error) {
            console.error('Error loading settings:', error);
            alert('Failed to load settings.');
        }
    }

    // --- Handle LLM Model Selection Change ---
    llmModelSelect.addEventListener('change', function() {
        const selectedKey = this.value;

        // Hide both sections first
        llmModelDetails.style.display = 'none';
        newLlmModelDetails.style.display = 'none';

        if (selectedKey === 'new-llm') {
            // Show new LLM form and clear its fields
            newLlmModelDetails.style.display = 'block';
            newLlmModelDetails.querySelectorAll('input, textarea').forEach(input => {
                input.value = '';
            });
        } else if (selectedKey && currentLlmSettingsData[selectedKey]) {
            // Show existing LLM details
            llmModelDetails.style.display = 'block';
            const selectedModelSettings = currentLlmSettingsData[selectedKey];

            // Populate LLM model details form
            document.getElementById('llm-model-name').value = selectedModelSettings.model || '';
            document.getElementById('llm-api-endpoint').value = selectedModelSettings.api_endpoint || '';
            document.getElementById('llm-api-key').value = selectedModelSettings.api_key || '';
            document.getElementById('llm-max-tokens').value = selectedModelSettings.max_tokens || '';
            document.getElementById('llm-temperature').value = selectedModelSettings.temperature || '';

            // Set model name input as readonly
            document.getElementById('llm-model-name').setAttribute('readonly', 'true');
        }
    });

    // --- Handle Save API Keys Form Submission ---
    apiKeyForm.addEventListener('submit', async function(event) {
        event.preventDefault();

        const apiKeysData = {
            GOOGLE_API_KEY: document.getElementById('google_api_key').value,
            GOOGLE_CSE_ID: document.getElementById('google_cse_id').value,
            BRAVE_API_KEY: document.getElementById('brave_api_key').value,
            // Reddit API keys are removed from the form and thus not sent
        };

        try {
            const response = await fetch('/save_settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ apiKeys: apiKeysData })
            });

            const result = await response.json();
            if (response.ok) {
                alert(result.message);
            } else {
                alert('Error saving API keys: ' + result.message);
            }
        } catch (error) {
            console.error('Error saving API keys:', error);
            alert('Failed to save API keys.');
        }
    });

    // --- Handle Save LLM Settings Form Submission ---
    llmSettingsForm.addEventListener('submit', async function(event) {
        event.preventDefault();

        const selectedKey = llmModelSelect.value;
        let updatedLlmSettings = { ...currentLlmSettingsData }; // Start with current data

        if (selectedKey === 'new-llm') {
            const newModelKey = document.getElementById('new-llm-key').value.trim();
            if (!newModelKey) {
                alert("Please provide a key for the new LLM model.");
                return;
            }
            if (updatedLlmSettings.hasOwnProperty(newModelKey)) {
                alert(`An LLM model with key "${newModelKey}" already exists. Please choose a different key or edit the existing model.`);
                return;
            }

            const newModelSettings = {
                model: document.getElementById('new-llm-model-name').value,
                api_endpoint: document.getElementById('new-llm-api-endpoint').value,
                api_key: document.getElementById('new-llm-api-key').value,
                max_tokens: parseFloat(document.getElementById('new-llm-max-tokens').value) || null,
                temperature: parseFloat(document.getElementById('new-llm-temperature').value) || null,
            };
            updatedLlmSettings[newModelKey] = newModelSettings;

        } else if (selectedKey && updatedLlmSettings.hasOwnProperty(selectedKey)) {
            // Update existing model
            updatedLlmSettings[selectedKey] = {
                model: document.getElementById('llm-model-name').value,
                api_endpoint: document.getElementById('llm-api-endpoint').value,
                api_key: document.getElementById('llm-api-key').value,
                max_tokens: parseFloat(document.getElementById('llm-max-tokens').value) || null,
                temperature: parseFloat(document.getElementById('llm-temperature').value) || null,
            };
        } else {
            alert("Please select an LLM model to edit or choose 'New LLM' to add a new one.");
            return;
        }

        try {
            const response = await fetch('/save_settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ llmSettings: updatedLlmSettings })
            });

            const result = await response.json();
            if (response.ok) {
                alert(result.message);
                loadSettings(); // Reload settings to update dropdown and state
                llmModelSelect.value = selectedKey === 'new-llm' ? '' : selectedKey; // Reset or keep selected
                llmModelSelect.dispatchEvent(new Event('change')); // Trigger change to update display
            } else {
                alert('Error saving LLM settings: ' + result.message);
            }
        } catch (error) {
            console.error('Error saving LLM settings:', error);
            alert('Failed to save LLM settings.');
        }
    });

    // --- Handle Delete LLM Model Button Click ---
    deleteLlmModelButton.addEventListener('click', async function() {
        const selectedKey = llmModelSelect.value;
        if (!selectedKey || selectedKey === "" || selectedKey === "new-llm") {
            alert("Please select an existing LLM model to delete.");
            return;
        }

        if (confirm(`Are you sure you want to delete the LLM model configuration for "${selectedKey}"?`)) {
            try {
                let updatedLlmSettings = { ...currentLlmSettingsData };
                if (updatedLlmSettings.hasOwnProperty(selectedKey)) {
                    delete updatedLlmSettings[selectedKey];

                    const response = await fetch('/save_settings', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ llmSettings: updatedLlmSettings })
                    });

                    const result = await response.json();
                    if (response.ok) {
                        alert(result.message);
                        loadSettings(); // Reload settings to update dropdown
                        llmModelDetails.style.display = 'none'; // Hide details section
                    } else {
                        alert('Error deleting LLM model: ' + result.message);
                    }
                } else {
                    alert(`LLM model configuration for "${selectedKey}" not found.`);
                }

            } catch (error) {
                console.error('Error deleting LLM model:', error);
                alert('Failed to delete LLM model.');
            }
        }
    });

    // Initial load of settings when the page loads
    loadSettings();
});