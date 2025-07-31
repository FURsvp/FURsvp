from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from events.models import Event, Group
from users.models import Profile, GroupDelegation, GroupRole
from two_factor.forms import TOTPDeviceForm as BaseTOTPDeviceForm
import base64

class UserRegisterForm(UserCreationForm):
    eula_agreement = forms.BooleanField(
        required=True,
        label="I agree to the End User License Agreement (EULA)",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_eula_agreement'
        }),
        error_messages={
            'required': 'You must agree to the End User License Agreement to create an account.'
        }
    )
    
    class Meta:
        model = User
        fields = ['username', 'email']

class UserProfileForm(forms.ModelForm):
    admin_groups = forms.CharField(
        required=False,
        label="Groups",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Type group names separated by commas...'
        })
    )
    clear_profile_picture = forms.BooleanField(required=False, label="Remove Profile Picture")
    can_post_blog = forms.BooleanField(required=False, label="Can post blog posts to Bluesky")

    class Meta:
        model = Profile
        fields = ['display_name', 'profile_picture_base64', 'discord_username', 'telegram_username', 'can_post_blog']
        widgets = {
            'display_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your display name'
            }),
            'discord_username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your Discord username'
            }),
            'telegram_username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your Telegram username'
            }),
            'profile_picture_base64': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            # Set initial value to comma-separated group names
            user_groups = Group.objects.filter(group_roles__user=self.instance.user)
            group_names = ', '.join([group.name for group in user_groups])
            self.fields['admin_groups'].initial = group_names
        if self.instance and self.instance.profile_picture_base64:
            self.initial['profile_picture_base64'] = self.instance.profile_picture_base64
        if not (self.instance and self.instance.user and self.instance.user.is_superuser):
            self.fields.pop('can_post_blog', None)

    def save(self, commit=True):
        # Get the admin_groups data before calling super().save()
        admin_groups_text = self.cleaned_data.get('admin_groups', '')
        
        # Save the profile first
        instance = super().save(commit=commit)
        
        # Then handle the group assignments
        if self.instance and self.instance.user:
            # Parse comma-separated group names
            group_names = [name.strip() for name in admin_groups_text.split(',') if name.strip()]
            
            # Find groups by name
            groups = Group.objects.filter(name__in=group_names)
            
            # Clear existing group roles
            GroupRole.objects.filter(user=self.instance.user).delete()
            
            # Add new GroupRoles
            for group in groups:
                GroupRole.objects.create(user=self.instance.user, group=group)
        
        return instance

class UserGroupManagementForm(forms.Form):
    """Form specifically for managing user groups in the administration panel"""
    admin_groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label="Groups",
        widget=forms.SelectMultiple(attrs={
            'class': 'tom-select-groups tom-select-custom',
            'multiple': True
        })
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # Set initial value to user's groups
        user_groups = Group.objects.filter(group_roles__user=user)
        self.fields['admin_groups'].initial = user_groups

    def save(self):
        """Only handle group assignments, don't touch profile data"""
        groups = self.cleaned_data.get('admin_groups', Group.objects.none())
        
        # Clear existing group roles
        GroupRole.objects.filter(user=self.user).delete()
        
        # Add new GroupRoles
        for group in groups:
            GroupRole.objects.create(user=self.user, group=group)

class UserPermissionForm(forms.Form):
    """Form for assigning permissions to users"""
    is_superuser = forms.BooleanField(
        required=False,
        label="Admin/Staff",
        help_text="Full administrative access"
    )
    can_post_blog = forms.BooleanField(
        required=False,
        label="Can Post Blog",
        help_text="Can create blog posts on Bluesky"
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # Set initial values
        self.fields['is_superuser'].initial = user.is_superuser
        self.fields['can_post_blog'].initial = user.profile.can_post_blog if hasattr(user, 'profile') else False

    def save(self):
        """Save permission changes"""
        is_superuser = self.cleaned_data.get('is_superuser', False)
        can_post_blog = self.cleaned_data.get('can_post_blog', False)
        
        # Update user permissions
        if self.user.is_superuser != is_superuser:
            self.user.is_superuser = is_superuser
            self.user.save()
        
        # Update profile permissions
        if hasattr(self.user, 'profile') and self.user.profile.can_post_blog != can_post_blog:
            self.user.profile.can_post_blog = can_post_blog
            self.user.profile.save()

class UserPublicProfileForm(forms.ModelForm):
    clear_profile_picture = forms.BooleanField(required=False, label="Remove Profile Picture")
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your email address'
    }))

    class Meta:
        model = Profile
        fields = ['display_name', 'discord_username', 'telegram_username', 'profile_picture_base64']
        widgets = {
            'display_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your display name'
            }),
            'discord_username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your Discord username'
            }),
            'telegram_username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your Telegram username'
            }),
            'profile_picture_base64': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.profile_picture_base64:
            self.initial['profile_picture_base64'] = self.instance.profile_picture_base64
        if self.instance and self.instance.user:
            self.initial['email'] = self.instance.user.email

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            if 'email' in self.cleaned_data:
                instance.user.email = self.cleaned_data['email']
                instance.user.save()
        return instance

class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name']

class RenameGroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name']

class AssistantAssignmentForm(forms.ModelForm):
    delegated_user = forms.ModelChoiceField(queryset=User.objects.filter(is_superuser=False).exclude(id=None), label="Assign User as Assistant")
    group = forms.ModelChoiceField(queryset=Group.objects.all(), label="For Group")

    class Meta:
        model = GroupDelegation
        fields = ['delegated_user', 'group']

    def __init__(self, *args, **kwargs):
        organizer_profile = kwargs.pop('organizer_profile', None)
        super().__init__(*args, **kwargs)
        if organizer_profile and organizer_profile.user:
            self.fields['group'].queryset = Group.objects.filter(group_roles__user=organizer_profile.user).distinct()
        if organizer_profile and organizer_profile.user:
            self.fields['delegated_user'].queryset = self.fields['delegated_user'].queryset.exclude(id=organizer_profile.user.id)

class UserPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs['class'] = 'form-control'

class GroupRoleForm(forms.ModelForm):
    class Meta:
        model = GroupRole
        fields = ['user', 'custom_label', 'can_post', 'can_manage_leadership'] 

class TOTPDeviceForm(BaseTOTPDeviceForm):
    pass 

class BlueskyBlogPostForm(forms.Form):
    title = forms.CharField(max_length=300, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Title'}))
    content = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Write your blog post here...', 'rows': 6})) 
