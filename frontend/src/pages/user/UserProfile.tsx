import ProfileSettings from '../../components/ProfileSettings';
import MFASettings from '../../components/MFASettings';

export default function UserProfile() {
  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <ProfileSettings />
      <MFASettings />
    </div>
  );
}
