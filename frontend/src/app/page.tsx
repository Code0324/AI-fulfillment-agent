import BackendConnection from "@/components/BackendConnection";

export default function Home() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-lg mx-auto p-8 w-full">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Amazon AI Fulfillment Assistant
          </h1>
          <p className="text-lg text-gray-600 mb-6">
            AI-powered order fulfillment workspace
          </p>
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-yellow-100 text-yellow-800 rounded-full text-sm font-medium">
            <span className="w-2 h-2 bg-yellow-500 rounded-full" />
            Status: Development
          </div>
        </div>
        <BackendConnection />
      </div>
    </main>
  );
}
