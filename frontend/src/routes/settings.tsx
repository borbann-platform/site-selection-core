import { createFileRoute } from "@tanstack/react-router";
import { Shell } from "../components/Shell";
import {
  Settings as SettingsIcon,
  Database,
  Bell,
  Shield,
  User,
} from "lucide-react";

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  return (
    <Shell>
      <div className="h-full w-full bg-black text-white overflow-y-auto custom-scrollbar">
        <div className="max-w-4xl mx-auto py-12 px-6">
          <div className="flex items-center gap-4 mb-8">
            <div className="p-3 bg-white/10 rounded-xl">
              <SettingsIcon size={32} className="text-emerald-400" />
            </div>
            <div>
              <h1 className="text-3xl font-bold">Settings</h1>
              <p className="text-white/60">
                Manage your preferences and account
              </p>
            </div>
          </div>

          <div className="grid gap-8">
            {/* General Settings */}
            <section className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <User size={20} className="text-blue-400" />
                Profile & Account
              </h2>
              <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden">
                <div className="p-6 border-b border-white/10 flex items-center justify-between">
                  <div>
                    <div className="font-medium">Display Name</div>
                    <div className="text-sm text-white/60">
                      How you appear to others
                    </div>
                  </div>
                  <div className="text-white/40">John Doe</div>
                </div>
                <div className="p-6 flex items-center justify-between">
                  <div>
                    <div className="font-medium">Email Address</div>
                    <div className="text-sm text-white/60">
                      Used for notifications
                    </div>
                  </div>
                  <div className="text-white/40">john@example.com</div>
                </div>
              </div>
            </section>

            {/* Data Preferences */}
            <section className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Database size={20} className="text-purple-400" />
                Data & Analysis
              </h2>
              <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden">
                <div className="p-6 border-b border-white/10 flex items-center justify-between">
                  <div>
                    <div className="font-medium">Default Search Radius</div>
                    <div className="text-sm text-white/60">
                      Base radius for site analysis
                    </div>
                  </div>
                  <select className="bg-black/50 border border-white/20 rounded px-3 py-1 text-sm">
                    <option>1 km</option>
                    <option>2 km</option>
                    <option>5 km</option>
                  </select>
                </div>
                <div className="p-6 flex items-center justify-between">
                  <div>
                    <div className="font-medium">Isochrone Mode</div>
                    <div className="text-sm text-white/60">
                      Default travel mode for catchments
                    </div>
                  </div>
                  <div className="flex bg-black/50 rounded-lg p-1 border border-white/10">
                    <button className="px-3 py-1 rounded bg-white/20 text-xs font-bold">
                      Walk
                    </button>
                    <button className="px-3 py-1 rounded text-white/40 text-xs font-bold hover:text-white">
                      Drive
                    </button>
                  </div>
                </div>
              </div>
            </section>

            {/* Notifications */}
            <section className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Bell size={20} className="text-yellow-400" />
                Notifications
              </h2>
              <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden">
                <div className="p-6 flex items-center justify-between">
                  <div>
                    <div className="font-medium">Report Ready Alerts</div>
                    <div className="text-sm text-white/60">
                      Email me when large reports are done
                    </div>
                  </div>
                  <div className="w-10 h-6 bg-emerald-500 rounded-full relative cursor-pointer">
                    <div className="absolute right-1 top-1 w-4 h-4 bg-white rounded-full shadow-sm" />
                  </div>
                </div>
              </div>
            </section>

            {/* Security */}
            <section className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Shield size={20} className="text-red-400" />
                Security
              </h2>
              <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden">
                <div className="p-6 flex items-center justify-between">
                  <div>
                    <div className="font-medium">API Keys</div>
                    <div className="text-sm text-white/60">
                      Manage access tokens
                    </div>
                  </div>
                  <button className="text-sm font-bold text-white/60 hover:text-white">
                    Manage
                  </button>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>
    </Shell>
  );
}
