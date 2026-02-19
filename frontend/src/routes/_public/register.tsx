import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useId, useMemo, useState } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";

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
    <div className="min-h-screen bg-background bg-noise relative flex flex-col items-center justify-center p-4">
      {/* Ambient orbs */}
      <div className="absolute top-1/4 left-1/3 w-96 h-96 bg-brand/[0.08] rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/3 w-80 h-80 bg-ai-accent/[0.06] rounded-full blur-3xl pointer-events-none" />

      {/* Logo */}
      <div className="mb-8 text-center z-10">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-gradient-to-br from-brand to-brand/70 text-brand-foreground text-2xl font-bold mb-4 glow-brand-sm mx-auto">
          B
        </div>
        <h1 className="text-xl font-semibold tracking-tight">Borbann</h1>
        <p className="text-sm text-muted-foreground/60 mt-1">
          AI-Powered Real Estate Intelligence
        </p>
      </div>

      {/* Glass form card */}
      <div className="glass-panel rounded-2xl p-6 w-full max-w-sm shadow-xl z-10">
        <h2 className="text-xl font-semibold mb-1">Create Account</h2>
        <p className="text-sm text-muted-foreground/70 mb-6">
          Sign up to access the Real Estate Platform
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 bg-destructive/[0.08] border border-destructive/25 rounded-lg text-destructive text-sm">
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
                className="bg-surface-2 border-white/[0.1] focus:border-brand/40 placeholder:text-muted-foreground/50"
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
                className="bg-surface-2 border-white/[0.1] focus:border-brand/40 placeholder:text-muted-foreground/50"
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
              className="bg-surface-2 border-white/[0.1] focus:border-brand/40 placeholder:text-muted-foreground/50"
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
              className="bg-surface-2 border-white/[0.1] focus:border-brand/40 placeholder:text-muted-foreground/50"
              placeholder="Min 8 characters"
            />
            {/* Password strength indicator */}
            {formData.password.length > 0 && (
              <div className="space-y-1">
                <div className="h-1.5 w-full bg-white/[0.06] rounded-full overflow-hidden">
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
              className="bg-surface-2 border-white/[0.1] focus:border-brand/40 placeholder:text-muted-foreground/50"
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
      </div>
    </div>
  );
}
