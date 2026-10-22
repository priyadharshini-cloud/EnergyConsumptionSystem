// ============================================
// LOGIN PAGE JAVASCRIPT
// ============================================

document.addEventListener("DOMContentLoaded", function () {

    // -------------------------------
    // NORMAL EMAIL LOGIN
    // -------------------------------

    const loginForm = document.getElementById("loginForm");

    if (loginForm) {
        loginForm.addEventListener("submit", async function (event) {
            event.preventDefault();

            const emailInput = document.getElementById("email");
            const passwordInput = document.getElementById("password");

            const email = emailInput.value.trim();
            const password = passwordInput.value;

            if (!email || !password) {
                alert("Please enter your email and password.");
                return;
            }

            try {
                const response = await fetch("/api/auth/login", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    credentials: "same-origin",
                    body: JSON.stringify({
                        email: email,
                        password: password
                    })
                });

                const data = await response.json();

                if (!response.ok) {
                    alert(data.error || "Login failed.");
                    return;
                }

                window.location.href = "/dashboard";

            } catch (error) {
                console.error("Normal login error:", error);
                alert("Unable to connect to the server.");
            }
        });
    }
});


// ============================================
// GOOGLE LOGIN
// IMPORTANT: THIS MUST BE GLOBAL
// ============================================

window.handleGoogleSignIn = async function (response) {

    console.log("Google callback received.");

    if (!response || !response.credential) {
        console.error("No Google credential received.");
        alert("Google sign-in did not return a credential.");
        return;
    }

    console.log("Sending Google credential to Flask...");

    try {

        const result = await fetch("/api/auth/google", {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            credentials: "same-origin",

            body: JSON.stringify({
                credential: response.credential
            })
        });

        console.log("Flask response status:", result.status);

        const data = await result.json();

        console.log("Flask response:", data);

        if (!result.ok) {
            alert(data.error || "Google sign-in failed.");
            return;
        }

        console.log("Google login successful.");
        console.log("Redirecting to dashboard...");

        // Give Flask session a moment to be stored,
        // then move to the main website.
        setTimeout(function () {
            window.location.replace("/dashboard");
        }, 300);

    } catch (error) {

        console.error("Google login error:", error);

        alert(
            "Google sign-in could not connect to the backend.\n\n" +
            "Make sure Flask is running on http://127.0.0.1:5000"
        );
    }
};