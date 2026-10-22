// ============================================
// LOGIN & REGISTRATION JS
// ============================================

document.addEventListener("DOMContentLoaded", function () {
  const tabLogin = document.getElementById("tabLogin");
  const tabRegister = document.getElementById("tabRegister");
  const formTitle = document.getElementById("formTitle");
  const formSubtitle = document.getElementById("formSubtitle");
  const nameGroup = document.getElementById("nameGroup");
  const fullNameInput = document.getElementById("fullName");
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const authForm = document.getElementById("authForm");
  const submitBtn = document.getElementById("submitBtn");
  const submitText = document.getElementById("submitText");
  const submitSpinner = document.getElementById("submitSpinner");
  const authAlert = document.getElementById("authAlert");
  const demoLoginBtn = document.getElementById("demoLoginBtn");

  let isRegisterMode = false;

  function showAlert(msg, isError = true) {
    authAlert.textContent = msg;
    authAlert.className = "alert-box " + (isError ? "error" : "success");
    authAlert.style.display = "block";
  }

  function hideAlert() {
    authAlert.style.display = "none";
  }

  function setLoading(loading, btnLabel) {
    if (loading) {
      submitBtn.disabled = true;
      submitSpinner.style.display = "inline-block";
      submitText.textContent = "Processing...";
    } else {
      submitBtn.disabled = false;
      submitSpinner.style.display = "none";
      submitText.textContent = btnLabel;
    }
  }

  // Switch to Sign In
  tabLogin.addEventListener("click", () => {
    isRegisterMode = false;
    tabLogin.classList.add("active");
    tabRegister.classList.remove("active");
    nameGroup.style.display = "none";
    fullNameInput.removeAttribute("required");
    formTitle.textContent = "Welcome back";
    formSubtitle.textContent = "Sign in to access your electricity consumption dashboard & bill forecast.";
    submitText.textContent = "Sign In to Dashboard";
    hideAlert();
  });

  // Switch to Create Account
  tabRegister.addEventListener("click", () => {
    isRegisterMode = true;
    tabRegister.classList.add("active");
    tabLogin.classList.remove("active");
    nameGroup.style.display = "block";
    fullNameInput.setAttribute("required", "true");
    formTitle.textContent = "Create an Account";
    formSubtitle.textContent = "Register with your details to start monitoring and predicting electricity bills.";
    submitText.textContent = "Create Account";
    hideAlert();
  });

  // One-click Demo Login
  if (demoLoginBtn) {
    demoLoginBtn.addEventListener("click", async () => {
      hideAlert();
      demoLoginBtn.disabled = true;
      demoLoginBtn.textContent = "Logging in...";

      try {
        const res = await fetch("/api/auth/demo-login", {
          method: "POST",
          headers: { "Content-Type": "application/json" }
        });
        const data = await res.json();
        if (res.ok) {
          showAlert("Demo access granted! Redirecting to dashboard...", false);
          setTimeout(() => {
            window.location.href = "/dashboard";
          }, 400);
        } else {
          showAlert(data.error || "Demo login failed.");
          demoLoginBtn.disabled = false;
          demoLoginBtn.textContent = "Quick Demo Login →";
        }
      } catch (err) {
        console.error(err);
        showAlert("Server connection error. Make sure Flask is running.");
        demoLoginBtn.disabled = false;
        demoLoginBtn.textContent = "Quick Demo Login →";
      }
    });
  }

  // Form submit handler
  authForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAlert();

    const email = emailInput.value.trim();
    const password = passwordInput.value;
    const name = fullNameInput.value.trim();

    if (!email || !password) {
      showAlert("Please enter both email and password.");
      return;
    }

    if (isRegisterMode && !name) {
      showAlert("Please enter your full name.");
      return;
    }

    const endpoint = isRegisterMode ? "/api/auth/register" : "/api/auth/login";
    const payload = isRegisterMode ? { name, email, password } : { email, password };
    const defaultLabel = isRegisterMode ? "Create Account" : "Sign In to Dashboard";

    setLoading(true, defaultLabel);

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (!res.ok) {
        showAlert(data.error || "Authentication failed.");
        setLoading(false, defaultLabel);
        return;
      }

      showAlert(data.message || "Success! Redirecting...", false);
      setTimeout(() => {
        window.location.href = "/dashboard";
      }, 500);

    } catch (err) {
      console.error("Auth error:", err);
      showAlert("Could not connect to the backend server. Make sure Flask is running on port 5000.");
      setLoading(false, defaultLabel);
    }
  });
});

// Google Sign-In Global Callback
window.handleGoogleSignIn = async function (response) {
  if (!response || !response.credential) {
    alert("Google authentication did not provide credentials.");
    return;
  }

  try {
    const res = await fetch("/api/auth/google", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential: response.credential })
    });
    const data = await res.json();

    if (res.ok) {
      window.location.href = "/dashboard";
    } else {
      alert(data.error || "Google Sign-in failed.");
    }
  } catch (err) {
    console.error("Google Auth error:", err);
    alert("Connection error during Google Sign-in.");
  }
};