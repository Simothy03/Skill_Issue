import { useNavigate } from 'react-router-dom';

export default function LandingPage() {
  return (
    <div className="bg-white">
      <main className="isolate">
        {/* Hero section */}
        <div className="relative pt-14">
          {/* <div
            aria-hidden="true"
            className="absolute inset-x-0 -top-40 -z-10 transform-gpu overflow-hidden blur sm:-top-80"
          >
            <div
              style={{
                clipPath:
                  'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)',
              }}
              className="relative left-[calc(50%-11rem)] aspect-[1155/678] w-[36.125rem] -translate-x-1/2 rotate-[30deg] bg-gradient-to-tr from-[#ff80b5] to-[#9089fc] opacity-30 sm:left-[calc(50%-30rem)] sm:w-[72.1875rem]"
            />
          </div> */}
          <div className="pt-12 pb-24 sm:pt-16 sm:pb-32 lg:pb-40">
            <div className="mx-auto max-w-7xl px-6 lg:px-8">
              <div className="mx-auto max-w-2xl text-center">
                <img
                  src="/images/Skill_Issue_Logo.png"
                  alt="Skill Issue Logo"
                  className="mx-auto h-auto w-60"
                />
                <p className="mt-8 text-pretty text-lg font-medium text-gray-500 sm:text-xl/8">
                  The Only Problem is You
                </p>
                <div className="mt-10 flex items-center justify-center gap-x-6">
                  <a
                    className="rounded-full bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
                    href="/login"
                  >
                    Get Started
                  </a>
                </div>
              </div>
            </div>
          </div>
          {/* <div
            aria-hidden="true"
            className="absolute inset-x-0 top-[calc(100%-13rem)] -z-10 transform-gpu overflow-hidden blur sm:top-[calc(100%-30rem)]"
          >
            <div
              style={{
                clipPath:
                  'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)',
              }}
              className="relative left-[calc(50%+3rem)] aspect-[1155/678] w-[36.125rem] -translate-x-1/2 bg-gradient-to-tr from-[#ff80b5] to-[#9089fc] opacity-30 sm:left-[calc(50%+36rem)] sm:w-[72.1875rem]"
            />
          </div> */}
        </div>
      </main>

      <div className="mx-auto max-w-7xl px-6 pt-8 pb-32 sm:pt-12 lg:px-8">
        <div className="mx-auto max-w-2xl">
          <h2 className="text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            About Skill Issue
          </h2>
          <p className="mt-6 text-lg leading-8 text-gray-600">
            We all know that practice does not make perfect. Practice might
            make proficient, or progress, or permanence. However, practice
            doesn't necessarily mean <i>improvement</i>. If we continuosuly
            practice errors and don't have the knowledge or foresight to fix
            these issues, they end up becoming <b>bad habits</b>.
          </p>
          <p className="mt-6 text-lg leading-8 text-gray-600">
            Recognizing any bad habits in your performance is an important part
            for improvement. <i>Skill Issue</i> aims to help players recognize
            their own consistent habits in their Chess gameplay and provide 
            actionable feedback to break out of these habits. 
          </p>
          <p className="mt-6 text-lg leading-8 text-gray-600">
            After all, you are the only one that can fix your bad habits. In 
            the same realm, every game you lose only hold one thing in common:
            You. In almost every game that we make mistakes, we are the issue. The better
            that we can recognize our mistakes and adopt the belief of internal
            locus of control, the better we can overcome our skill deficit.
          </p>
        </div>
      </div>
      <footer className="fixed inset-x-0 bottom-0 z-10 bg-white py-3 text-center shadow-t">
        <p className="text-sm text-gray-500">
          &copy; Skill Issue 2025
        </p>
      </footer>
    </div>
  )
}
