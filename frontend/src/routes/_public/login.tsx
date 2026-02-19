import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useId, useState } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";

export const Route = createFileRoute("/_public/login")({
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const formId = useId();
  const emailId = `${formId}-email`;
  const passwordId = `${formId}-password`;

  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await login(formData.email, formData.password);
      navigate({ to: "/", search: { district: undefined } });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
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
        <h2 className="text-xl font-semibold mb-1">Welcome back</h2>
        <p className="text-sm text-muted-foreground/70 mb-6">
          Sign in to your account
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 bg-destructive/[0.08] border border-destructive/25 rounded-lg text-destructive text-sm">
              {error}
            </div>
          )}

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
              className="bg-surface-2 border-white/[0.1] focus:border-brand/40 placeholder:text-muted-foreground/50"
              placeholder="Enter your password"
            />
          </div>

          <Button
            type="submit"
            className="w-full"
            disabled={isLoading}
          >
            {isLoading ? "Signing in..." : "Sign In"}
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            Don't have an account?{" "}
            <Link to="/register" className="text-brand hover:text-brand/80 hover:underline">
              Sign up
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
