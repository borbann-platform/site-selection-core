import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useId, useMemo, useState } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";

export const Route = createFileRoute("/_public/register")({
  component: RegisterPage,
});

function getPasswordStrength(password: string) {
  let score = 0;
  if (password.length >= 8) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[a-z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;

  if (score <= 1) return { level: "Weak", color: "bg-destructive", width: "w-1/4" } as const;
  if (score <= 2) return { level: "Fair", color: "bg-warning", width: "w-2/4" } as const;
  if (score <= 3) return { level: "Good", color: "bg-brand", width: "w-3/4" } as const;
  return { level: "Strong", color: "bg-success", width: "w-full" } as const;
}

function RegisterPage() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const formId = useId();
  const firstNameId = `${formId}-first-name`;
  const lastNameId = `${formId}-last-name`;
  const emailId = `${formId}-email`;
  const passwordId = `${formId}-password`;
  const confirmPasswordId = `${formId}-confirm-password`;

  const [formData, setFormData] = useState({
    email: "",
    password: "",
    confirmPassword: "",
    firstName: "",
    lastName: "",
  });

  const passwordStrength = useMemo(
    () => getPasswordStrength(formData.password),
    [formData.password],
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation guards
    if (formData.password !== formData.confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (formData.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    // Password strength check (uppercase, lowercase, number)
    const hasUppercase = /[A-Z]/.test(formData.password);
    const hasLowercase = /[a-z]/.test(formData.password);
    const hasNumber = /[0-9]/.test(formData.password);

    if (!hasUppercase || !hasLowercase || !hasNumber) {
      setError("Password must contain uppercase, lowercase, and a number");
      return;
    }

    setIsLoading(true);

    try {
      await register(
        formData.email,
        formData.password,
        formData.confirmPassword,
        formData.firstName,
        formData.lastName
      );
      navigate({ to: "/", search: { district: undefined } });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  return (
    <div className="min-h-screen bg-background flex flex-col md:flex-row">
      {/* Brand panel - top band on mobile, left half on desktop */}
      <div className="bg-gradient-to-br from-brand to-brand/80 md:w-1/2 flex flex-col items-center justify-center relative overflow-hidden px-8 py-12 md:py-0">
        {/* Decorative grid pattern */}
        <div
          className="absolute inset-0 opacity-10"
          style={{
            backgroundImage:
              "radial-gradient(circle, white 1px, transparent 1px)",
            backgroundSize: "24px 24px",
          }}
        />
        <div className="relative z-10 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 md:w-20 md:h-20 rounded-2xl bg-white/20 backdrop-blur-sm text-white text-3xl md:text-4xl font-bold mb-4 md:mb-6">
            B
          </div>
          <h1 className="text-2xl md:text-3xl font-bold text-white mb-2">
            Borbann
          </h1>
          <p className="text-white/80 text-sm md:text-base">
            AI-Powered Real Estate Intelligence
          </p>
        </div>
      </div>

      {/* Form panel */}
      <div className="md:w-1/2 flex items-center justify-center p-6 md:p-12">
        <Card className="w-full max-w-sm bg-card border-border">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold text-foreground">
              Create Account
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Sign up to access the Real Estate Platform
            </p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-md text-destructive text-sm">
                  {error}
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor={firstNameId} className="text-foreground">
                    First Name
                  </Label>
                  <Input
                    id={firstNameId}
                    name="firstName"
                    type="text"
                    value={formData.firstName}
                    onChange={handleChange}
                    required
                    className="bg-input border-border text-foreground placeholder:text-muted-foreground"
                    placeholder="John"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor={lastNameId} className="text-foreground">
                    Last Name
                  </Label>
                  <Input
                    id={lastNameId}
                    name="lastName"
                    type="text"
                    value={formData.lastName}
                    onChange={handleChange}
                    required
                    className="bg-input border-border text-foreground placeholder:text-muted-foreground"
                    placeholder="Doe"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor={emailId} className="text-foreground">
                  Email
                </Label>
                <Input
                  id={emailId}
                  name="email"
                  type="email"
                  value={formData.email}
                  onChange={handleChange}
                  required
                  className="bg-input border-border text-foreground placeholder:text-muted-foreground"
                  placeholder="john@example.com"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor={passwordId} className="text-foreground">
                  Password
                </Label>
                <Input
                  id={passwordId}
                  name="password"
                  type="password"
                  value={formData.password}
                  onChange={handleChange}
                  required
                  minLength={8}
                  className="bg-input border-border text-foreground placeholder:text-muted-foreground"
                  placeholder="Min 8 characters"
                />
                {/* Password strength indicator */}
                {formData.password.length > 0 && (
                  <div className="space-y-1">
                    <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${passwordStrength.color} ${passwordStrength.width}`}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Strength: {passwordStrength.level}
                    </p>
                  </div>
                )}
                <p className="text-xs text-muted-foreground">
                  Must contain uppercase, lowercase, and a number
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor={confirmPasswordId} className="text-foreground">
                  Confirm Password
                </Label>
                <Input
                  id={confirmPasswordId}
                  name="confirmPassword"
                  type="password"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  required
                  className="bg-input border-border text-foreground placeholder:text-muted-foreground"
                  placeholder="Repeat your password"
                />
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={isLoading}
              >
                {isLoading ? "Creating account..." : "Create Account"}
              </Button>

              <p className="text-center text-sm text-muted-foreground">
                Already have an account?{" "}
                <Link to="/login" className="text-brand hover:text-brand/80 hover:underline">
                  Sign in
                </Link>
              </p>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
